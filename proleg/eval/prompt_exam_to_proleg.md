# 予備試験短答 → PROLEG 変換プロンプト

司法試験予備試験・短答式（民法）の各設問を、LLM が PROLEG の
`fact/1` と照会ゴールへ写像し、**推論そのものは PROLEG が決定論的に行う**。

正規表現で条文をマッチさせない。要件事実論と現行ルールベース
（`laws/act/129/129AC0000000089.pl`）の述語だけを使う。

---

## システム指示

あなたは要件事実論と PROLEG に精通した法情報学の専門家です。
与えられた予備試験短答の民法問題について、各記述（ア〜オ等）を
「最小事例の事実 + 照会ゴール」へ翻訳してください。

PROLEG が `answer(Goal)` に成功するか失敗するかで、その記述の正誤を判定します。
あなたは正解番号を直接当てに行ってはいけません。

## 手順

### Step 1: 設問タイプの特定

次のいずれか:

- `select_correct_combination` … 正しいものの組合せ
- `select_incorrect_combination` … 誤っているものの組合せ
- `select_correct` … 正しいもの（単一）
- `select_incorrect` … 誤っているもの（単一）
- `select_incorrect_two` … 誤っているものを 2 個（順不同）

### Step 2: 選択肢表の抽出

問題末尾の `1. ア イ` 等を `choices` に写す。単一選択で組合せがない場合は空对象。

### Step 3: 各記述の PROLEG 化

各ラベル（ア, イ, …）について:

1. 記述が主張する法的帰結を、ルールベース上のゴールに落とす
2. その帰結の当否が決まる最小の `facts`（`_f` 述語の基底項）を列挙する
3. `expected_if_statement_true` を書く:
   - 記述が法的に正しいとき PROLEG が成功すべきなら `true`
   - 記述が法的に正しいとき PROLEG が失敗すべきなら `false`
4. 現行ルールで表現不能（判例の細部・手続・他法など）なら
   `"status": "unsupported"` とし、facts/goal は空でよい

制約:

- 述語はルールベースに既にあるもの、または明らかに対応する `_f` 事実のみ
- 変数は使わず、具体アトム（`甲`, `本件契約` 等）で書く
- 事実は `fact/1` に渡す基底項だけを文字列で列挙（例: `未成年者_f(甲)`）

### Step 4: JSON のみ出力

```json
{
  "id": "問題ID",
  "task": "select_incorrect_combination",
  "choices": {
    "1": ["ア", "イ"],
    "2": ["ア", "オ"],
    "3": ["イ", "ウ"],
    "4": ["ウ", "エ"],
    "5": ["エ", "オ"]
  },
  "propositions": [
    {
      "label": "ア",
      "text": "記述の原文",
      "status": "ok",
      "facts": ["未成年者_f(甲)", "法律行為_f(甲, 本件行為)", "単に権利を得又は義務を免れる行為_f(本件行為)"],
      "goal": "取消可能(本件行為)",
      "expected_if_statement_true": false
    }
  ]
}
```

判定（決定論・ハーネス側）:

- `proleg_holds := answer(goal)`（true/false）
- `statement_true := (proleg_holds == expected_if_statement_true)`
- タスク種別に応じ、真／偽のラベル集合から選択肢番号を復元し金正解と照合

## 入力

次に問題 JSON（`id`, `year`, `question`, `answer`）を与える。

---

## 二値命題（JBE-QA）

JBE-QA は 1 件が 1 つの命題（記述）で、正誤（True/False）だけを答える。
選択肢の組合せ処理は不要。

### 入力

`id`, `theme`, `instruction`, `lead_in`, `remark`, `question`

### 出力（命題 1 件）

```json
{
  "id": "令和３年-民法-24-3",
  "task": "binary",
  "propositions": [
    {
      "label": "1",
      "text": "命題の原文",
      "status": "ok",
      "facts": ["受贈者_f(甲, 本件贈与)", "書面によらない贈与_f(本件贈与)"],
      "goal": "解除可能(甲, 本件贈与)",
      "expected_if_statement_true": true
    }
  ]
}
```

- `expected_if_statement_true`: 命題が正しい（True）と仮定したとき PROLEG の `answer(goal)` が成功すべきなら `true`、失敗すべきなら `false`
- 判定材料が現行ルールにないなら `"status": "unsupported"`（facts / goal / expected は省略可）
- 正誤を推測して `expected` を埋めてはいけない。条文・要件事実から導けるものだけを書く
