# PROLEG

民法を [PROLEG](https://research.nii.ac.jp/~ksatoh/)（PROlog-based LEGal reasoning support system）形式で記述し、SWI-Prolog 上で推論・評価するための環境です。

現状は **民法のルールベースが一部のみ実装** の段階です（後述「現状と既知の課題」）。

## 構成

| パス | 説明 |
|---|---|
| `prolegEng3.pl` | PROLEG エンジン本体（upstream のまま） |
| `LICENSE-prolegEng3.txt` | エンジンのライセンス（MIT） |
| `prompt_template.md` | 条文 → PROLEG ルール生成用 Chain-of-Instructions プロンプト |
| `gen_minpo.pl.py` | 民法条文 markdown から `.pl` の骨組みを生成するスクリプト（一部条文は手書きルールを注入） |
| `check.pl` | コンパイル / style_check / library(check) / plunit の統合スクリプト（現状は合成テスト） |
| `eval/` | 予備試験短答を用いた LLM → PROLEG → 決定論採点の評価ハーネス（後述） |

ルールベース本体は法令 markdown と同じディレクトリに置きます。

```
laws/act/129/129AC0000000089.md   # 民法（条文）
laws/act/129/129AC0000000089.pl   # 民法（PROLEG ルール）
```

## 出典・ライセンス

`prolegEng3.pl` は次のリポジトリから取得しています。

- Upstream: [liviorobaldo/compliancecheckers](https://github.com/liviorobaldo/compliancecheckers)（`PROLEG/prolegEng3.pl`）
- License: MIT（`LICENSE-prolegEng3.txt`）
- PROLEG の設計: Ken Satoh et al., NII（要件事実論に基づく法的推論）

評価データの出典とライセンスは後述「評価ハーネス」を参照してください。

## 使い方

### 推論

```sh
swipl -l proleg/prolegEng3.pl -l laws/act/129/129AC0000000089.pl
```

```prolog
?- messageoff.
?- assert(fact(未成年者_f(甲))).
?- assert(fact(法律行為_f(甲, 本件契約))).
?- assert(fact(法定代理人の同意なし_f(本件契約))).
?- answer(取消可能(本件契約)).
```

### チェック

```sh
swipl proleg/check.pl
```

## ルール形式

```prolog
効果(引数) <= 要件1_f(引数), 要件2_f(引数).
exception(効果(引数), 例外事由_f(引数)).
fact(入力事実_f(値)).
```

- 述語名・変数名は日本語
- 入力事実（ファクト）は `_f` 接尾辞
- ルールの左辺は法的効果、右辺は要件事実
- `exception/2` で抗弁・再抗弁を表現

## ルール生成の方針

正規表現による条文パターンマッチは行いません。NII の手法に沿い、要件事実論に基づいてルールを作成します。

1. 条文を要件事実論の観点で分解（主要件事実・抗弁・再抗弁）
2. PROLEG 形式へ変換
3. SWI-Prolog のコンパイル / lint / 推論テストで検証

## 評価ハーネス（`eval/`）

予備試験短答（民法）の各命題について、LLM が「事実（`facts`）と照会ゴール（`goal`）」を作り、PROLEG の `answer/1` の成否で命題の正誤を決定論的に判定します。LLM は正解番号を直接当てません。

```text
問題文 ─(LLM: prompt_exam_to_proleg.md)→ 予測 JSON（facts / goal / expected）
   └→ run_eval.py → solve.pl → PROLEG answer/1（true / false）
                    └→ 命題の正誤 → 選択肢番号 / True-False と金正解を照合
```

| ファイル | 役割 |
|---|---|
| `eval/data/shihou_yobi_minpo.jsonl` | 予備試験短答（民法）225 問（2011〜2025 年、各年 No.1〜15） |
| `eval/prompt_exam_to_proleg.md` | 命題 → facts / goal / expected への変換プロンプト（組合せ問題と二値問題の両方） |
| `eval/solve.pl` | 1 照会の推論ドライバ（エンジン・ルール・facts JSON を読み、true/false を書き出す） |
| `eval/run_eval.py` | 採点本体（`--smoke` / `--prepare-prompts` / 採点） |
| `eval/predictions/` | 予測 JSON（現状は 2011 年第 1 問のパイロットと smoke 用） |

```sh
python3 proleg/eval/run_eval.py --smoke              # 動作確認
python3 proleg/eval/run_eval.py --prepare-prompts    # 問題ごとの入力 JSON を eval/prompts/ に展開
python3 proleg/eval/run_eval.py --predictions proleg/eval/predictions   # 採点
```

### データの出典

- 予備試験短答（民法）: [ShigyoBench（todo1111/shigyobench）](https://huggingface.co/datasets/todo1111/shigyobench) の `shihou_yobi` から民法科目を抽出。ライセンスは CC-BY-NC-4.0（非営利・研究利用）。元データは法務省公開の過去問。
- JBE-QA（司法試験短答・二値命題）: 採点ロジックは実装済みだが、データは HF の gated リポジトリ（`nguyenthanhasia/japanese-bar-exam-qa-v2`）のためまだ取得していない。ライセンス欄も空欄のため、取得後に確認が必要。

## 実施したこと（作業履歴）

1. エンジン導入: `prolegEng3.pl` と MIT ライセンスを `proleg/` に配置。SWI-Prolog 10.0.2 で契約成立・例外推論を確認。
2. プロンプト作成: `prompt_template.md`（要件事実論に基づく Chain-of-Instructions）。
3. 民法ルール生成: `gen_minpo.pl.py` で `laws/act/129/129AC0000000089.pl` を生成。第1編の代表条文に手書きルールを注入し、残りは TODO 付きの骨組み。
4. 旧ファイルの削除: 旧 `proleg/act/129/` と `tools/md_to_proleg.py` を削除（方針により不使用）。
5. 不具合修正:
   - ルールファイルのエンジン読み込みパスを `../../../proleg/prolegEng3.pl` に修正（`gen_minpo.pl.py` も同様）。従来は `laws/` を起点にしていたため、単体ロードでエンジンが読めていなかった。
   - 第112条の本文が参照する `代理権消滅_f` を、新規の `代理権消滅` ルールに接続。
6. ルール追加（第1次バッチ）: 第97条（到達）、第98条の2（受領能力）、第111条（代理権の消滅）、第122条（追認）、第124条第1項（追認の要件）。
7. 評価ハーネス構築: 予備試験民法 225 問の抽出、変換プロンプト、推論ドライバ、採点スクリプト（組合せ・単一・二値タスク）。
8. パイロット: 2011 年第 1 問で、ア（true）・イ（true）・ウ（false）・エ（false）を PROLEG の判定と金正解で一致させた。オは未実装（第731条・第738条）のため unsupported。

## 現状と既知の課題

- ルール数: 民法の実装済みルールは約 60 件。条文 1,300 件超は TODO のまま。そのため、評価 225 問の大半は unsupported になる見込み。
- 全件の採点はまだ実行していない。
- `check.pl` は合成テスト（plunit）のままで、評価ハーネスへの置換は未実施。
- 生成されたルールファイルにシングルトン変数の警告が多数ある（既存ルールの変数命名に起因）。
- `run_eval.py` の `select_incorrect_two`（2 個選択）の採点は、命題ラベルと金正解の番号を照合できていない。
- プロンプト内の誤字（「空对象」）が残っている。
- 税法の評価データは未決定（日本の税法の正誤付き短答データは確認できず）。
