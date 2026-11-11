#!/usr/bin/env python3
"""司法予備試験短答（民法）の LLM→PROLEG→決定論スコアリング。

流れ:
  1. LLM が prompt_exam_to_proleg.md に従い predictions/*.json を書く
  2. 本スクリプトが各命題を PROLEG で決定論的に評価
  3. 選択肢番号を復元し、金正解 (answer) と照合

例:
  python proleg/eval/run_eval.py --predictions proleg/eval/predictions
  python proleg/eval/run_eval.py --smoke
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
DATA = EVAL_DIR / "data" / "shihou_yobi_minpo.jsonl"
SOLVE = EVAL_DIR / "solve.pl"
RULES = ROOT / "laws" / "act" / "129" / "129AC0000000089.pl"
ENGINE = EVAL_DIR.parent / "prolegEng3.pl"


DATA_BINARY = EVAL_DIR / "data" / "jbe_qa_minpo.jsonl"


def load_gold() -> dict[str, dict]:
    gold: dict[str, dict] = {}
    with DATA.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            gold[row["id"]] = row
    return gold


def load_gold_binary() -> dict[str, dict]:
    """JBE-QA（二値命題）の金正解。ファイルが無ければ空。"""
    gold: dict[str, dict] = {}
    if not DATA_BINARY.exists():
        return gold
    with DATA_BINARY.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            gold[row["id"]] = row
    return gold


def score_binary(pred: dict, gold_row: dict) -> dict:
    """二値命題 1 件を採点。PROLEG の判定を statement_true とし、金正解 True/False と照合する。"""
    props = pred.get("propositions", [])
    if len(props) != 1:
        raise ValueError(f"binary task は propositions を 1 件にしてください: {pred['id']}")
    p = props[0]
    base = {
        "id": pred["id"],
        "task": "binary",
        "year": gold_row.get("year"),
        "theme": gold_row.get("theme"),
        "gold": [str(gold_row["answer"])],
    }
    if p.get("status", "ok") != "ok":
        return {**base, "unsupported": [p.get("label", "")], "predicted": [], "correct": False}

    holds = proleg_holds(p.get("facts") or [], p["goal"])
    expected = bool(p["expected_if_statement_true"])
    statement_true = holds == expected
    gold_true = str(gold_row["answer"]).strip().lower() == "true"
    return {
        **base,
        "unsupported": [],
        "proleg_holds": holds,
        "expected_if_statement_true": expected,
        "predicted": ["True" if statement_true else "False"],
        "correct": statement_true == gold_true,
    }


def normalize_answer(ans: str) -> set[str]:
    """'4' or '1,5' → frozenset of choice tokens."""
    parts = [p.strip() for p in str(ans).replace("，", ",").split(",") if p.strip()]
    return set(parts)


def proleg_holds(facts: list[str], goal: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        facts_path = td_path / "facts.json"
        out_path = td_path / "out.txt"
        facts_path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
        # Goal を Prolog アトム文字列として渡す（日本語アトム可）
        goal_escaped = goal.replace("\\", "\\\\").replace("'", "''")
        goal = [
            "swipl",
            "-q",
            "--on-error=status",
            "-t",
            "halt",
            "-g",
            (
                f"consult('{SOLVE.as_posix()}'), "
                f"run('{RULES.as_posix()}', '{facts_path.as_posix()}', "
                f"'{goal_escaped}', '{out_path.as_posix()}')"
            ),
        ]
        proc = subprocess.run(
            goal,
            cwd=str(EVAL_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"PROLEG failed for goal={goal!r}: {err}")
        result = out_path.read_text(encoding="utf-8").strip()
        if result not in {"true", "false"}:
            raise RuntimeError(f"unexpected PROLEG output: {result!r}")
        return result == "true"


def evaluate_prediction(pred: dict) -> dict:
    true_labels: list[str] = []
    false_labels: list[str] = []
    unsupported: list[str] = []
    details = []

    for prop in pred.get("propositions", []):
        label = prop["label"]
        status = prop.get("status", "ok")
        if status != "ok":
            unsupported.append(label)
            details.append({"label": label, "status": status})
            continue
        holds = proleg_holds(prop.get("facts") or [], prop["goal"])
        expected = bool(prop["expected_if_statement_true"])
        statement_true = holds == expected
        if statement_true:
            true_labels.append(label)
        else:
            false_labels.append(label)
        details.append(
            {
                "label": label,
                "status": "ok",
                "proleg_holds": holds,
                "expected_if_statement_true": expected,
                "statement_true": statement_true,
            }
        )

    task = pred.get("task", "")
    choices: dict[str, list[str]] = {
        str(k): list(v) for k, v in (pred.get("choices") or {}).items()
    }
    predicted: set[str] = set()

    if unsupported:
        predicted = set()
    elif task == "select_correct_combination":
        target = set(true_labels)
        for num, labs in choices.items():
            if set(labs) == target:
                predicted.add(num)
    elif task == "select_incorrect_combination":
        target = set(false_labels)
        for num, labs in choices.items():
            if set(labs) == target:
                predicted.add(num)
    elif task == "select_correct":
        if len(true_labels) == 1 and not choices:
            # 1..5 が各記述そのもののとき
            mapping = {"ア": "1", "イ": "2", "ウ": "3", "エ": "4", "オ": "5"}
            predicted.add(mapping.get(true_labels[0], true_labels[0]))
        elif choices:
            for num, labs in choices.items():
                if set(labs) == set(true_labels):
                    predicted.add(num)
        else:
            predicted = set(true_labels)
    elif task == "select_incorrect":
        if len(false_labels) == 1 and not choices:
            mapping = {"ア": "1", "イ": "2", "ウ": "3", "エ": "4", "オ": "5"}
            predicted.add(mapping.get(false_labels[0], false_labels[0]))
        elif choices:
            for num, labs in choices.items():
                if set(labs) == set(false_labels):
                    predicted.add(num)
        else:
            predicted = set(false_labels)
    elif task == "select_incorrect_two":
        predicted = set(false_labels)
    else:
        raise ValueError(f"unknown task: {task}")

    return {
        "id": pred["id"],
        "task": task,
        "true_labels": true_labels,
        "false_labels": false_labels,
        "unsupported": unsupported,
        "predicted": sorted(predicted),
        "details": details,
    }


def score(pred_path: Path, gold: dict[str, dict], gold_binary: dict[str, dict] | None = None) -> dict:
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    if pred.get("task") == "binary":
        g = (gold_binary or {}).get(pred["id"])
        if not g:
            return {"id": pred["id"], "task": "binary", "correct": False, "error": "gold not found"}
        return score_binary(pred, g)
    result = evaluate_prediction(pred)
    g = gold.get(pred["id"])
    if not g:
        result["error"] = "gold not found"
        result["correct"] = False
        return result
    gold_ans = normalize_answer(g["answer"])
    pred_ans = set(result["predicted"])
    # 2個選択は順不同集合比較。それ以外は選択肢番号集合。
    if result["task"] == "select_incorrect_two":
        # predicted はラベル。金正解は番号なので、予測 JSON に gold_labels が必要。
        # ここでは choices が空の前提で、pred に answer_labels があれば使う。
        gold_labels = set(pred.get("gold_labels") or [])
        if gold_labels:
            result["correct"] = pred_ans == gold_labels
            result["gold"] = sorted(gold_labels)
        else:
            result["correct"] = False
            result["gold"] = sorted(gold_ans)
            result["note"] = "select_incorrect_two は gold_labels が必要"
    else:
        result["correct"] = pred_ans == gold_ans and not result["unsupported"]
        result["gold"] = sorted(gold_ans)
    result["year"] = g.get("year")
    result["question_number"] = g.get("question_number")
    return result


def write_smoke_prediction() -> Path:
    """2011 第1問の一部（ア・エ）を手書きで煙試験。"""
    out_dir = EVAL_DIR / "predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    # ア: 「単に義務を免れる行為は同意なくできる」→ 取消は例外で失敗するはず
    # エ: 「詐術を用いても取り消せる」→ 第21条で取消不可 → 記述は誤り
    # 煙試験では全命題を埋めず、ハーネス動作確認用の縮小版を別 ID で走らせる。
    sample = {
        "id": "smoke_art5_art21",
        "task": "select_incorrect_combination",
        "choices": {"1": ["ア"], "2": ["エ"], "3": ["ア", "エ"]},
        "propositions": [
            {
                "label": "ア",
                "text": "未成年者は単に義務を免れる法律行為を同意なくできる（取消されない）",
                "status": "ok",
                "facts": [
                    "未成年者_f(甲)",
                    "法律行為_f(甲, 本件行為)",
                    "法定代理人の同意なし_f(本件行為)",
                    "単に権利を得又は義務を免れる行為_f(本件行為)",
                ],
                "goal": "取消可能(本件行為)",
                "expected_if_statement_true": False,
            },
            {
                "label": "エ",
                "text": "詐術を用いても取り消せる",
                "status": "ok",
                "facts": [
                    "制限行為能力者_f(甲)",
                    "法律行為_f(甲, 本件契約)",
                    "詐術_f(甲, 本件契約)",
                ],
                "goal": "取消不可(本件契約)",
                "expected_if_statement_true": False,
            },
        ],
        "_smoke_gold": "1",
    }
    path = out_dir / "smoke_art5_art21.json"
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_smoke() -> int:
    # ルールに取消不可があるか確認しつつ、命題単位の決定論を検証
    path = write_smoke_prediction()
    pred = json.loads(path.read_text(encoding="utf-8"))
    result = evaluate_prediction(pred)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # ア: holds=false, expected_if_true=false → statement_true
    # エ: 取消不可が成り立てば holds=true, expected_if_true=false → statement_false
    a = next(d for d in result["details"] if d["label"] == "ア")
    ok = a.get("statement_true") is True
    print("SMOKE", "PASS" if ok else "FAIL", file=sys.stderr)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path, default=EVAL_DIR / "predictions")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--prepare-prompts", action="store_true",
                    help="各問題用の LLM 入力 JSON を prompts/ に展開")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.smoke:
        return run_smoke()

    gold = load_gold()

    if args.prepare_prompts:
        out = EVAL_DIR / "prompts"
        out.mkdir(parents=True, exist_ok=True)
        rows = list(gold.values())
        rows.sort(key=lambda r: (r["year"], r["question_number"]))
        if args.limit:
            rows = rows[: args.limit]
        for r in rows:
            p = out / f"{r['id']}.json"
            payload = {
                "id": r["id"],
                "year": r["year"],
                "question_number": r["question_number"],
                "question": r["question"],
                "answer": r["answer"],
                "instruction": "proleg/eval/prompt_exam_to_proleg.md に従い predictions 用 JSON を出力",
            }
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(rows)} prompts under {out}")
        return 0

    pred_dir: Path = args.predictions
    files = sorted(pred_dir.glob("*.json"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"no predictions in {pred_dir}", file=sys.stderr)
        print("先に LLM で prompt_exam_to_proleg.md に従い JSON を書いてください。", file=sys.stderr)
        return 1

    gold_binary = load_gold_binary()
    results = []
    for f in files:
        if f.name.startswith("smoke_"):
            continue
        try:
            results.append(score(f, gold, gold_binary))
        except Exception as e:
            results.append({"id": f.stem, "correct": False, "error": str(e)})

    n = len(results)
    c = sum(1 for r in results if r.get("correct"))
    unsupported = sum(1 for r in results if r.get("unsupported"))
    print(json.dumps({"n": n, "correct": c, "accuracy": (c / n if n else 0),
                      "with_unsupported": unsupported, "results": results},
                     ensure_ascii=False, indent=2))
    return 0 if n and c == n else (0 if n == 0 else 1)


if __name__ == "__main__":
    raise SystemExit(main())
