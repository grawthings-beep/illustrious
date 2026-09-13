# Illustrious Studio

**複数のNIKKEキャラを、同じ一枚の画像に生成するためのRunPod用リポジトリ。**

学習時と同じ **Nova Anime XL IL v19.0** を使用。キャラごとにLoRA・プロンプト・適用領域を分けます。日本語の操作画面と、ComfyUIに読み込める1〜4人用ワークフローを同梱しています。

- 水着エレグ、水着ラピ、白シンデレラ、シンデレラ黒ビキニを登録済み。
- キャラごとの髪色・目色・衣装・ポーズ、LoRA強度を編集できます。
- 枠のドラッグで移動、右下の丸でサイズ変更。数値での指定も可能。
- 共通の背景と各キャラの指定を、**一つの潜在画像・一つのサンプラー**で生成します。
- PNGダウンロード、ワークフローJSON書き出し、PNGへの生成設定保存に対応。

## RunPodで起動する

### 1. Podの設定

GPU付きPodを使用し、HTTPポートに **8188** を追加してください。環境変数は以下の名前で、作成済みのSecretを割り当てます。

| 環境変数名 | RunPodの設定値 |
| --- | --- |
| `CIVITAI_TOKEN` | `{{ RUNPOD_SECRET_CIVITAI_TOKEN }}` |
| `HF_TOKEN` | `{{ RUNPOD_SECRET_HF_TOKEN }}` |

この記法は**RunPodの設定画面**で展開されます。ターミナルにこの文字列をexportする必要はありません。`.env.example`は説明用で、自動読み込みはしません。トークンの値をGitHubに登録・コミットする必要もありません。[RunPod公式のSecret設定](https://docs.runpod.io/pods/templates/secrets)

LoRA学習に使ったPodをそのまま使用できます。起動済みの別のComfyUIが8188を使っている場合は、そのサービスを停止するか、後述の別ポートを使ってください。

### 2. RunPodのターミナルに貼る

初回はこの3行を実行します。

```bash
cd /workspace
git clone https://github.com/grawthings-beep/illustrious.git illustrious-generation
bash /workspace/illustrious-generation/scripts/start.sh
```

以後の起動は最後の1行だけです。ターミナルにはログが出続けます。**Ctrl+CでStudioが停止します。**

別ポートが必要な場合は、RunPodのHTTPポートに8189を追加してから起動します。

```bash
ILLUSTRIOUS_PORT=8189 bash /workspace/illustrious-generation/scripts/start.sh
```

初回はComfyUIと必要パッケージを専用環境に用意します。学習用の`/opt/venvs/core`を書き換えず、既存のCUDA PyTorchを保持します。GPU計算・CLIP・実際のComfyUIノードを確認してから、チェックポイントを取得します。6.94 GBのダウンロードは中断後の再開とSHA-256照合に対応しています。

### 3. 画面を開く

RunPodの **Connect → HTTP Service :8188** を開き、URLの末尾に **`/illustrious/`** を付けます。

```text
https://<PodのID>-8188.proxy.runpod.net/illustrious/
```

通常のComfyUIは同じURLの`/`です。Studioの右上からも開けます。

## 学習済みLoRAの配置

起動時に次の順に探し、登録済みのSHA-256と形式を確認します。

1. `/workspace/models/loras/<ファイル名>`
2. `/workspace/illustrious-loras/<ファイル名>`
3. `/workspace/illustrious-nikke-lora/runs/<ジョブ名>/*/checkpoints/<ファイル名>`

**学習が終わった同じPodなら、残っている完成LoRAを自動で取り込みます。再送不要です。** 別Podにしかない黒ビキニなどは転送してください。未配置のキャラは画面に表示され、そのキャラを含む生成は開始できません。

| キャラ | ファイル名 | トリガー |
| --- | --- | --- |
| 水着エレグ | `illustrious_swimsuit_elegg.safetensors` | `sw1melegg` |
| 水着ラピ | `illustrious_swimsuit_rapi.safetensors` | `sw1mrapi` |
| 白シンデレラ | `illustrious_cinderella_white.safetensors` | `wh1tec1nde` |
| シンデレラ黒ビキニ | `illustrious_cinderella_black_bikini.safetensors` | `b1k1c1nde` |

チェックポイントは`/workspace/models/checkpoints/novaAnimeXL_ilV190.safetensors`を再利用します。重み・元画像・サンプル・秘密トークンはこのリポジトリに含みません。

### PCから新しいPodへ送る場合

PCでこのリポジトリを取得し、ダウンロード済みLoRAが入ったフォルダを指定してパックを作れます。Python 3.11以上が必要です。

```powershell
python scripts/pack_loras.py --source "C:\LoRAを保存したフォルダ" --output "C:\転送用\illustrious-loras.tar.gz"
& "$env:USERPROFILE\Downloads\runpodctl.exe" send "C:\転送用\illustrious-loras.tar.gz"
```

表示された`runpodctl receive ...`を**RunPodのターミナル**に貼り、受信後に展開します。

```bash
cd /workspace
# ここでPCに表示された runpodctl receive ... を実行
tar -xzf illustrious-loras.tar.gz -C /workspace
bash /workspace/illustrious-generation/scripts/start.sh
```

`--source`は複数指定できます。黒ビキニだけ送る場合は`--character cinderella_black_bikini`を追加します。パックは完成LoRAの名前とSHA-256を照合し、学習画像・中間epoch・サンプルを含めません。JupyterのGUIアップロードは不要です。[RunPod公式の転送手順](https://docs.runpod.io/pods/storage/transfer-files)

## 複数キャラを生成する

1. まず**2人**で、水着エレグと水着ラピを選ぶ。
2. 左右の枠と、各キャラ欄のプロンプトを設定する。
3. 共通欄に`beach, ocean, blue sky, daylight`など背景を書く。
4. 「この配置で生成する」を押す。初期値は28 steps / CFG 5.5 / LoRA 0.8。

髪色・目色を変えるときは、そのキャラ欄の元の色タグを**置き換えます**。例：`blonde hair`→`blue hair`。着替えでは`yellow bikini, heart cutout`など元の衣装タグを外し、`red dress`などに置き換えてください。トリガーは自動付与します。

これは変更の指示を分けられる設計です。衣装別LoRAの学習内容には元衣装の偏りがあるため、どんな衣装にも確実に着替えられる保証はありません。元衣装が強く残るときはLoRA強度を下げて調整します。別衣装への汎用性は生成比較で確認してください。

枠は特徴を適用する領域の目安で、骨格・人数を固定するものではありません。重なり・接触の多いポーズ、3〜4人では混ざりや重複が起きることがあります。人数を増やすとLoRAごとの計算が増え、生成時間・メモリ使用量も増えます。今回の重みを使ったGPUでの生成品質評価は未実施です。

## 完成画像とワークフロー

- 画面の「PNGをダウンロード」から取得できます。
- Pod内のPNG：`/workspace/illustrious-data/output/illustrious/`
- 「ワークフロー保存 ↓」で編集した構成をJSON保存できます。
- PNGにもComfyUIワークフローとStudioの設定を記録します。PNG/JSONをComfyUIへドラッグすると再利用できます。
- 同梱のGUI用JSON：[`workflows/`](workflows/)。API形式は[`workflows/api/`](workflows/api/)。起動時にComfyUIのワークフロー一覧にも初回コピーします。

| ワークフロー | 初期キャラ |
| --- | --- |
| `01-single.json` | 水着エレグ |
| `02-two-characters.json` | 水着エレグ＋水着ラピ |
| `03-three-characters.json` | 上記＋白シンデレラ |
| `04-four-characters.json` | 上記＋シンデレラ黒ビキニ |

PNGをまとめて持ち帰る場合、**RunPodのターミナル**で：

```bash
tar -czf /workspace/illustrious-images.tar.gz -C /workspace/illustrious-data/output illustrious
runpodctl send /workspace/illustrious-images.tar.gz
```

PCのPowerShellで保存先フォルダに移動し、表示された受信用のコードを使って`runpodctl.exe receive <コード>`を実行します。画像が生成される前には、この画像フォルダはまだ存在しません。

## Dockerと拡張

[`Dockerfile`](Dockerfile)はPyTorch 2.11.0 / CUDA 13.0の公式イメージをdigestで固定しています。重みと秘密トークンはビルドせず、Pod起動時に読み込みます。

GitHubのActions → **Build RunPod image** → **Run workflow** で`ghcr.io/grawthings-beep/illustrious:latest`を作成できます。**ビルド完了前はこのイメージは使用できません。** RunPod用設定例は[`deploy/runpod-template.json`](deploy/runpod-template.json)。GHCRのパッケージがprivateの場合は、RunPodのレジストリ認証設定かパッケージの公開設定が必要です。

追加キャラの登録、Hugging Face上のLoRA取得、構成の詳細、検証内容は[`docs/WORKFLOWS.md`](docs/WORKFLOWS.md)を参照してください。
