const $ = (id) => document.getElementById(id);
const colors = ["#79acdf", "#e7a0b0", "#d2be80", "#82c9ac"];
const negative = "worst quality, low quality, lowres, bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, text, watermark, signature";
$("negative").value = negative;
let catalog, characters = [], activePrompt = null, pollTimer = null, socket, busy = false;
const clientId = crypto.randomUUID();

function status(message, error = false) { $("status").textContent = message; $("status").classList.toggle("error", error); }
async function request(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.error === "string" ? result.error : JSON.stringify(result.node_errors || result.error || result));
  return result;
}
function preset(id) { return catalog.characters.find((c) => c.id === id); }
function defaultRegion(index, count) { return [index / count + 0.02, 0.02, 1 / count - 0.04, 0.96]; }
function updateAvailability() {
  const missing = characters.filter((c) => !preset(c.id).available).map((c) => preset(c.id).label);
  if (!catalog.checkpoint.available) missing.unshift("Nova Anime XL IL v19.0");
  $("availability").textContent = missing.length ? `未配置のモデル: ${[...new Set(missing)].join("、")}。起動ログの保存先へ配置してから、ページを再読み込みしてください。` : "";
  $("generate").disabled = busy || missing.length > 0;
}
function setCount(count) {
  const old = characters;
  characters = Array.from({ length: count }, (_, index) => old[index] || { id: catalog.characters[index].id, prompt: catalog.characters[index].prompt, negative: "", strength: 0.8 });
  characters.forEach((c, i) => { c.region = defaultRegion(i, count); });
  if (count === 1) { $("width").value = 1024; $("height").value = 1024; }
  else { $("width").value = count >= 3 ? 1536 : 1344; $("height").value = count >= 3 ? 1024 : 896; }
  document.querySelectorAll("[data-count]").forEach((b) => b.classList.toggle("selected", Number(b.dataset.count) === count));
  renderCharacters(); renderRegions(); updateAvailability();
}
function renderCharacters() {
  $("characters").replaceChildren();
  characters.forEach((character, index) => {
    const box = document.createElement("section"); box.className = "character"; box.style.setProperty("--region-color", colors[index]);
    box.innerHTML = `<div class="character-top"><span>${String(index + 1).padStart(2, "0")}</span><select aria-label="キャラ${index + 1}"></select><span class="trigger"></span></div><label>このキャラの髪色・目色・衣装・ポーズ</label><textarea class="char-prompt" rows="3" aria-label="キャラ${index + 1}のプロンプト"></textarea><div class="strength"><label>LoRA強度</label><input type="range" min="0" max="1.5" step="0.05" aria-label="キャラ${index + 1}のLoRA強度"><output></output></div><details><summary>位置・サイズと個別ネガティブ</summary><div class="region-fields"></div><label>このキャラだけ避けたい特徴</label><textarea class="char-negative" rows="2"></textarea></details>`;
    const select = box.querySelector("select");
    catalog.characters.forEach((item) => { const option = document.createElement("option"); option.value = item.id; option.textContent = item.label + (item.available ? "" : "（未配置）"); select.append(option); });
    select.value = character.id;
    select.onchange = () => { const next = preset(select.value); character.id = next.id; character.prompt = next.prompt; renderCharacters(); renderRegions(); updateAvailability(); };
    box.querySelector(".trigger").textContent = preset(character.id).trigger;
    const text = box.querySelector(".char-prompt"); text.value = character.prompt; text.oninput = () => { character.prompt = text.value; };
    const neg = box.querySelector(".char-negative"); neg.value = character.negative; neg.oninput = () => { character.negative = neg.value; };
    const strength = box.querySelector("input[type=range]"); strength.value = character.strength;
    const output = box.querySelector("output"); output.textContent = character.strength.toFixed(2);
    strength.oninput = () => { character.strength = Number(strength.value); output.textContent = character.strength.toFixed(2); };
    ["左(%)", "上(%)", "幅(%)", "高さ(%)"].forEach((title, field) => {
      const label = document.createElement("label"); label.textContent = title;
      const input = document.createElement("input"); input.type = "number"; input.min = 0; input.max = 100; input.step = 1; input.value = Math.round(character.region[field] * 100); input.dataset.regionField = `${index}-${field}`;
      input.onchange = () => { character.region[field] = Number(input.value) / 100; renderRegions(); };
      label.append(input); box.querySelector(".region-fields").append(label);
    });
    $("characters").append(box);
  });
}
function renderRegions() {
  $("layout").style.aspectRatio = `${Number($("width").value)} / ${Number($("height").value)}`;
  $("regions").replaceChildren();
  characters.forEach((character, index) => {
    const region = document.createElement("div"); region.className = "region"; region.style.setProperty("--region-color", colors[index]);
    region.innerHTML = `<span class="region-label"></span><span class="region-number">${String(index + 1).padStart(2, "0")}</span><span class="resize"></span>`;
    region.querySelector(".region-label").textContent = preset(character.id).label;
    const paint = () => { const [x,y,w,h] = character.region; Object.assign(region.style, { left: `${x*100}%`, top: `${y*100}%`, width: `${w*100}%`, height: `${h*100}%` }); };
    paint();
    region.onpointerdown = (event) => {
      if (event.button !== 0) return;
      event.preventDefault(); region.setPointerCapture(event.pointerId);
      const resizing = event.target.classList.contains("resize"), bounds = $("regions").getBoundingClientRect(), initial = [...character.region], startX = event.clientX, startY = event.clientY;
      region.onpointermove = (e) => {
        const dx = (e.clientX-startX)/bounds.width, dy = (e.clientY-startY)/bounds.height;
        if (resizing) character.region = [initial[0],initial[1],Math.max(.08,Math.min(1-initial[0],initial[2]+dx)),Math.max(.08,Math.min(1-initial[1],initial[3]+dy))];
        else character.region = [Math.max(0,Math.min(1-initial[2],initial[0]+dx)),Math.max(0,Math.min(1-initial[3],initial[1]+dy)),initial[2],initial[3]];
        paint();
        character.region.forEach((v,i) => { document.querySelector(`[data-region-field="${index}-${i}"]`).value = Math.round(v*100); });
      };
      const finish = () => { region.onpointermove = null; region.onpointerup = null; region.onpointercancel = null; };
      region.onpointerup = finish; region.onpointercancel = finish;
    };
    $("regions").append(region);
  });
}
function scene() {
  const result = { prompt: $("scene-prompt").value, negative: $("negative").value, characters: structuredClone(characters) };
  ["width","height","steps","cfg","seed","feather"].forEach((key) => { result[key] = Number($(key).value); });
  return result;
}
function downloadJSON(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function build() { return request("/illustrious/workflow", { method: "POST", headers: { "Content-Type":"application/json" }, body: JSON.stringify(scene()) }); }
function finish() { activePrompt = null; busy = false; clearTimeout(pollTimer); updateAvailability(); }
async function pollHistory() {
  if (!activePrompt) return;
  const id = activePrompt;
  try {
    const history = await request(`/history/${encodeURIComponent(id)}`);
    if (activePrompt !== id) return;
    const item = history[id];
    if (item?.status?.status_str === "error") { status("生成中にエラーが発生しました。ComfyUIのログを確認してください。", true); finish(); return; }
    if (item?.status?.completed) {
      const images = Object.values(item.outputs || {}).flatMap((out) => out.images || []).filter((image) => image.type === "output");
      if (!images.length) { status("生成は終了しましたが、保存画像が見つかりません。ComfyUIのログを確認してください。", true); finish(); return; }
      $("gallery").replaceChildren();
      images.forEach((image) => {
        const url = "/view?" + new URLSearchParams({filename:image.filename, subfolder:image.subfolder || "", type:"output"});
        const picture = document.createElement("img"); picture.src=url; picture.alt="生成した複数キャラの画像"; picture.className="result-image";
        const footer=document.createElement("div"); footer.className="image-footer";
        const caption=document.createElement("span"); caption.textContent=image.filename;
        const link=document.createElement("a"); link.href=url; link.download=image.filename; link.textContent="PNGをダウンロード ↓";
        footer.append(caption,link); $("gallery").append(picture,footer);
      });
      $("progress-bar").style.width="100%"; status("生成完了。画像とワークフローを保存しました。"); finish(); return;
    }
  } catch(error) { status(`接続を確認しています: ${error.message}`, true); }
  if (activePrompt) pollTimer = setTimeout(pollHistory, 2000);
}
function connect() {
  const url = new URL("/ws", location.href); url.protocol = location.protocol === "https:" ? "wss:" : "ws:"; url.searchParams.set("clientId", clientId);
  socket = new WebSocket(url);
  socket.onopen = () => { $("connection").textContent="接続済み"; $("connection").classList.add("online"); };
  socket.onclose = () => { $("connection").textContent="再接続中"; $("connection").classList.remove("online"); setTimeout(connect, 3000); };
  socket.onmessage = (message) => {
    if (typeof message.data !== "string") return;
    const event=JSON.parse(message.data), data=event.data;
    if (!activePrompt || (data.prompt_id && data.prompt_id !== activePrompt)) return;
    if (event.type === "progress") { const percent=Math.round(data.value/data.max*100); $("progress-bar").style.width=`${percent}%`; status(`生成中 ${data.value} / ${data.max} ステップ`); }
    if (event.type === "execution_start") status("モデルを読み込んでいます。初回は少し時間がかかります。");
    if (event.type === "execution_error" || event.type === "execution_interrupted") { status(data.exception_message || "生成が中断されました。", true); finish(); }
  };
}
$("count-options").onclick = (event) => { if (event.target.dataset.count) setCount(Number(event.target.dataset.count)); };
$("reset-layout").onclick = () => { characters.forEach((c,i) => { c.region=defaultRegion(i,characters.length); }); renderCharacters(); renderRegions(); };
$("width").onchange=renderRegions; $("height").onchange=renderRegions;
$("export").onclick=async () => { try { downloadJSON((await build()).workflow,"illustrious-scene.json"); status("ワークフローを保存しました。ComfyUIに読み込めます。"); } catch(error) {status(error.message,true);} };
$("generate").onclick=async () => {
  if (busy) return;
  busy = true; updateAvailability();
  try {
    if ($("random-seed").checked) $("seed").value=crypto.getRandomValues(new Uint32Array(1))[0];
    const built=await build();
    const queued=await request("/prompt",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:built.prompt,client_id:clientId,extra_data:{extra_pnginfo:{workflow:built.workflow,illustrious_scene:built.scene}}})});
    activePrompt=queued.prompt_id; $("progress-bar").style.width="0%"; status("生成キューに追加しました。"); pollHistory();
  } catch(error) { status(error.message,true); finish(); }
};
try { catalog=await request("/illustrious/catalog"); setCount(2); connect(); status($("generate").disabled ? "画面の準備ができました。生成には、上に表示されたモデルの配置が必要です。" : "準備完了。キャラと配置を選んで生成できます。"); }
catch(error) { status(`接続できません: ${error.message}`,true); }
