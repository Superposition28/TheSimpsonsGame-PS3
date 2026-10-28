"use strict";
const $ = id => document.getElementById(id);
const state = {file:null, filesOffset:0, idOffset:0, rawOffset:0, raw:false, graph:null, nodes:[], edges:[], scale:1, tx:0, ty:0, token:0};
const hex = n => "0x" + Number(n).toString(16).toUpperCase();
const shortName = path => path.replaceAll("\\","/").split("/").pop();
const el = (tag, text, className) => {const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
const params = () => ({view:$("view").value,cross:$("cross").checked?"1":"0",language:$("language").value});
async function api(name, values={}) {const response=await fetch("/api/"+name+"?"+new URLSearchParams(values));const data=await response.json();if(!response.ok)throw new Error(data.error||response.statusText);return data;}
function failure(error) {$("status").textContent="Error: "+error.message;$("status").className="error";}
function bytes(n){return n<1024?n+" B":n<1048576?(n/1024).toFixed(1)+" KiB":(n/1048576).toFixed(1)+" MiB";}
function status(text){$("status").className="";$("status").textContent=text;}
async function listFiles(reset=true){
  if(reset)state.filesOffset=0;
  const result=await api("files",{...params(),level:$("level").value,q:$("search").value,format:$("format").value,shared:$("shared").checked?"1":"0",offset:state.filesOffset});
  $("fileCount").textContent=result.total.toLocaleString();$("fileList").replaceChildren();
  for(const file of result.files){const button=el("button",undefined,"file-row"+(state.file?.id===file.id?" selected":""));button.dataset.id=file.id;button.title=file.path;
    button.append(el("span",shortName(file.member||file.path),"file-name"),el("span",file.format+" · "+file.view+" · "+bytes(file.size),"file-path"),el("span",file.path,"file-path"));
    button.onclick=()=>selectFile(file.id).catch(failure);$("fileList").append(button);}
  $("filePage").textContent=result.total?`${state.filesOffset+1}–${Math.min(state.filesOffset+result.limit,result.total)}`:"No matches";
  $("previousFiles").disabled=!state.filesOffset;$("nextFiles").disabled=state.filesOffset+result.limit>=result.total;
}
function targetButton(target, alternate=false){const button=el("button",`${target.view} · ${target.level} · ${shortName(target.member||target.path)}`,"target"+(alternate?" alt":""));button.title=target.path+"\n"+target.target_label;button.onclick=()=>selectFile(target.id).catch(failure);return button;}
function idCard(observation){
  const card=el("div",undefined,"identifier");card.append(el("span",observation.namespace,"pill"),el("span",observation.role,"pill"));
  const value=el("div",observation.value,"value");value.title="Show this stored ID and its target files";value.onclick=()=>isolate(observation);card.append(value);
  card.append(el("div",`${hex(observation.offset)} · ${observation.region} · ${observation.endian} · ${observation.width} bytes`,"offset"),el("p",observation.label,"description"));
  if(observation.doc){const link=el("a","Format evidence");link.href="/docs/"+observation.doc;link.target="_blank";link.rel="noopener";card.append(link);}
  const result=observation.resolution;
  if(result){card.append(el("div",result.status+` · ${result.candidate_files} candidate file(s)`,"resolution"+(result.status==="ambiguous"?" ambiguous":"")));
    for(const target of result.targets)card.append(targetButton(target));
    if(result.alternatives.length){const details=el("details");details.append(el("summary",`Other copies / alternatives (${result.candidate_files-result.targets.length}; first ${result.alternatives.length} shown)`));for(const target of result.alternatives)details.append(targetButton(target,true));card.append(details);}
    if(result.excluded_cross_level)card.append(el("p",`${result.excluded_cross_level} definition rows excluded by level scope`,"description"));
  }else if(observation.role==="value")card.append(el("p","Identifier meaning is unresolved; no structural file edge claimed.","description"));
  return card;
}
async function selectFile(id){
  const token=++state.token;state.idOffset=0;state.rawOffset=0;$("byteOffset").value="0x0";status("Reading file and resolving nearest copies…");
  const result=await api("file",{...params(),id,offset:0});if(token!==state.token)return;state.file=result.file;
  for(const button of document.querySelectorAll(".file-row"))button.classList.toggle("selected",Number(button.dataset.id)===id);
  const info=$("fileInfo");info.replaceChildren(el("strong",state.file.member||shortName(state.file.path)),el("div",state.file.path,"mono"),el("div",`${state.file.view} · ${state.file.level} · ${state.file.language} · ${bytes(state.file.size)}`),el("p",state.file.status));
  if(state.file.sha256){const checksum=el("details");checksum.append(el("summary","SHA-256"),el("div",state.file.sha256,"mono"));info.append(checksum);}
  if(state.file.locator!=="{}"){const source=el("details");source.append(el("summary","Original source coordinates"),el("pre",JSON.stringify(JSON.parse(state.file.locator),null,2),"mono"));info.append(source);}
  $("graphTitle").textContent=shortName(state.file.member||state.file.path);
  if(state.raw)await loadWords();else showIds(result);
  const graph=await api("graph",{...params(),id,depth:$("depth").value,maximum:$("maximum").value,incoming:$("incoming").checked?"1":"0"});
  if(token!==state.token)return;setGraph(graph);status(`${graph.files.length} files · ${graph.identifiers.length} stored reference IDs · inputs are read-only`);
}
function showIds(result){$("identifiers").replaceChildren(...result.identifiers.map(idCard));$("idPage").textContent=`${result.total?state.idOffset+1:0}–${Math.min(state.idOffset+60,result.total)} / ${result.total}`;$("previousIds").disabled=!state.idOffset;$("nextIds").disabled=state.idOffset+60>=result.total;}
async function loadIds(){if(state.file)showIds(await api("file",{...params(),id:state.file.id,offset:state.idOffset}));}
async function loadWords(){
  if(!state.file)return;const result=await api("words",{...params(),id:state.file.id,offset:state.rawOffset,unaligned:$("unaligned").checked?"1":"0"});$("identifiers").replaceChildren();
  for(const row of result.words){const card=el("div",undefined,"raw-word");card.append(el("div",hex(row.offset),"offset"),el("div",row.raw.match(/../g).join(" "),"raw-bytes"),el("div",`BE ${row.be.toString(16).padStart(8,"0").toUpperCase()} · LE ${row.le.toString(16).padStart(8,"0").toUpperCase()}`));
    for(const match of row.matches){const button=el("button",`${match.endian} → ${match.namespace}: ${match.resolution.status} (${match.resolution.candidate_files} files)`,"candidate");button.onclick=()=>isolate({...match,id:`raw-${row.offset}-${match.namespace}-${match.endian}`,file:state.file.id,offset:row.offset,region:"payload / file bytes",width:match.value.length/2,label:"Raw byte equality; not a verified field reference",role:"raw candidate"});card.append(button);}
    $("identifiers").append(card);}
  $("idPage").textContent=`${hex(state.rawOffset)}–${hex(result.next_offset)} / ${bytes(result.size)}`;$("previousIds").disabled=!state.rawOffset;$("nextIds").disabled=result.next_offset+4>result.size;state.rawStep=result.step;
}
function isolate(observation){
  const targets=observation.resolution?.targets||[];const isRaw=observation.role==="raw candidate";const files=[state.file,...targets];const id="i"+observation.id;
  const edges=[{source:"f"+state.file.id,target:id,kind:isRaw?"raw":"structural",label:observation.namespace},...targets.map(t=>({source:id,target:"f"+t.id,kind:isRaw?"raw":observation.resolution.status==="ambiguous"?"ambiguous":observation.confidence,label:observation.resolution.status}))];
  setGraph({files:[...new Map(files.map(f=>[f.id,f])).values()],identifiers:[observation],edges,focus:state.file.id,truncated:false,notice:isRaw?"RAW CANDIDATE: these bytes equal a known ID. Namespace and reference semantics have not been established for this field.":"Single documented ID neighborhood; click a target file to continue."});
}
const canvas=$("graph"),ctx=canvas.getContext("2d");let dragging=null,pan=null,hover=null,frame=null,iteration=0;
function setGraph(graph){
  state.graph=graph;const nodes=[];const count=graph.identifiers.length;
  graph.files.forEach((file,index)=>nodes.push({key:"f"+file.id,file,x:file.id===graph.focus?0:650+(index%3)*30,y:file.id===graph.focus?0:(index-graph.files.length/2)*92,w:230,h:58,focus:file.id===graph.focus}));
  graph.identifiers.forEach((id,index)=>nodes.push({key:"i"+id.id,observation:id,x:310,y:(index-(count-1)/2)*62,w:215,h:47}));
  const keys=new Map(nodes.map(n=>[n.key,n]));state.nodes=nodes;state.edges=graph.edges.filter(e=>keys.has(e.source)&&keys.has(e.target)).map(e=>({...e,a:keys.get(e.source),b:keys.get(e.target)}));
  $("graphNotice").textContent=(graph.truncated?`Showing up to ${graph.maximum} nodes; graph is limited. Page through IDs in the inspector. `:"")+graph.notice;$("graphNotice").className="notice"+(graph.truncated||graph.notice.startsWith("RAW")?" warn":"");
  iteration=0;if(frame)cancelAnimationFrame(frame);layout();fit();
}
function layout(){
  const nodes=state.nodes;if(iteration<110){
    for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
      const a=nodes[i],b=nodes[j];let dx=b.x-a.x,dy=b.y-a.y;if(Math.abs(dx)<250&&Math.abs(dy)<65){const move=(65-Math.abs(dy))*.12;const direction=dy===0?(i%2?1:-1):Math.sign(dy);if(!a.focus&&dragging!==a)a.y-=move*direction;if(!b.focus&&dragging!==b)b.y+=move*direction;}
    }iteration++;frame=requestAnimationFrame(layout);
  }draw();
}
function fit(){if(!state.nodes.length)return;const w=canvas.clientWidth,h=canvas.clientHeight;const xs=state.nodes.map(n=>n.x),ys=state.nodes.map(n=>n.y);const minX=Math.min(...xs)-150,maxX=Math.max(...xs)+150,minY=Math.min(...ys)-80,maxY=Math.max(...ys)+80;state.scale=Math.max(.06,Math.min(1.2,(w-30)/(maxX-minX),(h-30)/(maxY-minY)));state.tx=w/2-(maxX+minX)/2*state.scale;state.ty=h/2-(maxY+minY)/2*state.scale;draw();}
function rounded(x,y,w,h,r){ctx.beginPath();ctx.roundRect(x-w/2,y-h/2,w,h,r);}
function color(kind){return kind==="provenance"?"#657c98":kind==="raw"||kind==="ambiguous"?"#e3a35e":kind==="association"?"#83ace8":"#51bfae";}
function trim(text,length){text=String(text||"");return text.length>length?text.slice(0,length-1)+"…":text;}
function draw(){
  const ratio=devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;if(canvas.width!==Math.floor(w*ratio)||canvas.height!==Math.floor(h*ratio)){canvas.width=w*ratio;canvas.height=h*ratio;}ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);ctx.translate(state.tx,state.ty);ctx.scale(state.scale,state.scale);
  for(const e of state.edges){ctx.strokeStyle=color(e.kind);ctx.globalAlpha=.65;ctx.lineWidth=1.2/Math.sqrt(state.scale);ctx.setLineDash(e.kind==="provenance"||e.kind==="raw"||e.kind==="ambiguous"?[6,5]:[]);ctx.beginPath();ctx.moveTo(e.a.x,e.a.y);ctx.lineTo(e.b.x,e.b.y);ctx.stroke();const dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,angle=Math.atan2(dy,dx),x=e.a.x+dx*.65,y=e.a.y+dy*.65;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-9*Math.cos(angle-.4),y-9*Math.sin(angle-.4));ctx.moveTo(x,y);ctx.lineTo(x-9*Math.cos(angle+.4),y-9*Math.sin(angle+.4));ctx.stroke();}
  ctx.globalAlpha=1;ctx.setLineDash([]);
  for(const n of state.nodes){const id=n.observation;ctx.fillStyle=n.focus?"#193e43":id?"#102a2b":"#19283c";ctx.strokeStyle=n===hover?"#ffffff":n.focus?"#72e0d2":id?"#468e83":"#577597";ctx.lineWidth=n.focus?2:1;rounded(n.x,n.y,n.w,n.h,7);ctx.fill();ctx.stroke();ctx.textAlign="center";
    ctx.fillStyle=id?"#9be6d9":"#e3edf9";ctx.font="11px ui-monospace,monospace";ctx.fillText(trim(id?id.value:shortName(n.file.member||n.file.path),30),n.x,n.y-5);
    ctx.font="9px system-ui,sans-serif";ctx.fillStyle="#9cafc7";ctx.fillText(trim(id?`${hex(id.offset)} · ${id.namespace}`:`${n.file.view} · ${n.file.level} · ${n.file.format}`,38),n.x,n.y+12);
  }
}
function position(event){const r=canvas.getBoundingClientRect();return{x:(event.clientX-r.left-state.tx)/state.scale,y:(event.clientY-r.top-state.ty)/state.scale};}
function hit(p){return [...state.nodes].reverse().find(n=>Math.abs(n.x-p.x)<n.w/2&&Math.abs(n.y-p.y)<n.h/2);}
canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);const p=position(e);dragging=hit(p);pan=dragging?null:{x:e.clientX,y:e.clientY,tx:state.tx,ty:state.ty};};
canvas.onpointermove=e=>{const p=position(e);if(dragging){dragging.x=p.x;dragging.y=p.y;draw();return;}if(pan){state.tx=pan.tx+e.clientX-pan.x;state.ty=pan.ty+e.clientY-pan.y;draw();return;}hover=hit(p);const tip=$("tooltip");if(hover){const r=canvas.getBoundingClientRect();tip.textContent=hover.file?`${hover.file.path}\n${hover.file.status}`:`${hover.observation.namespace}\n${hover.observation.value}\n${hex(hover.observation.offset)} · ${hover.observation.region}\n${hover.observation.label}`;tip.style.display="block";tip.style.left=Math.min(e.clientX-r.left+12,r.width-300)+"px";tip.style.top=Math.min(e.clientY-r.top+12,r.height-110)+"px";}else tip.style.display="none";draw();};
canvas.onpointerup=()=>{dragging=null;pan=null;};canvas.onpointerleave=()=>{$("tooltip").style.display="none";hover=null;draw();};
canvas.ondblclick=e=>{const n=hit(position(e));if(n?.file)selectFile(n.file.id).catch(failure);else if(n?.observation){$("identifiers").replaceChildren(idCard(n.observation));}};
canvas.onwheel=e=>{e.preventDefault();const before=position(e),r=canvas.getBoundingClientRect();state.scale=Math.min(3,Math.max(.04,state.scale*Math.exp(-e.deltaY*.001)));state.tx=e.clientX-r.left-before.x*state.scale;state.ty=e.clientY-r.top-before.y*state.scale;draw();};
new ResizeObserver(()=>{draw();}).observe(canvas);
$("fit").onclick=fit;
$("export").onclick=()=>{if(!state.graph)return;const link=el("a");link.href=URL.createObjectURL(new Blob([JSON.stringify(state.graph,null,2)],{type:"application/json"}));link.download="file-connections-neighborhood.json";link.click();URL.revokeObjectURL(link.href);};
$("previousFiles").onclick=()=>{state.filesOffset=Math.max(0,state.filesOffset-80);listFiles(false).catch(failure);};$("nextFiles").onclick=()=>{state.filesOffset+=80;listFiles(false).catch(failure);};
let searchTimer;$("search").oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>listFiles().catch(failure),350);};
for(const key of ["level","view","format","shared"])$(key).onchange=()=>listFiles().catch(failure);
for(const key of ["language","cross","depth","maximum","incoming"])$(key).onchange=()=>{if(state.file)selectFile(state.file.id).catch(failure);};
$("typedTab").onclick=()=>{state.raw=false;$("typedTab").classList.add("active");$("rawTab").classList.remove("active");$("rawControls").hidden=true;loadIds().catch(failure);};
$("rawTab").onclick=()=>{state.raw=true;$("rawTab").classList.add("active");$("typedTab").classList.remove("active");$("rawControls").hidden=false;loadWords().catch(failure);};
$("readWords").onclick=()=>{const value=Number($("byteOffset").value);if(!Number.isSafeInteger(value)||value<0){failure(new Error("Enter a non-negative byte offset, such as 0x100"));return;}state.rawOffset=value;loadWords().catch(failure);};
$("previousIds").onclick=()=>{if(state.raw){state.rawOffset=Math.max(0,state.rawOffset-64*(state.rawStep||4));$("byteOffset").value=hex(state.rawOffset);loadWords().catch(failure);}else{state.idOffset=Math.max(0,state.idOffset-60);loadIds().catch(failure);}};
$("nextIds").onclick=()=>{if(state.raw){state.rawOffset+=64*(state.rawStep||4);$("byteOffset").value=hex(state.rawOffset);loadWords().catch(failure);}else{state.idOffset+=60;loadIds().catch(failure);}};
$("closeModal").onclick=()=>$("modal").close();
$("coverage").onclick=async()=>{try{const data=await api("catalog");$("modalTitle").textContent="Documentation coverage & interpretation limits";$("modalBody").replaceChildren(el("p",data.policy));const table=el("table");for(const f of data.formats){const row=el("tr"),cell=el("td"),a=el("a",f.title);a.href="/docs/"+f.doc;a.target="_blank";a.rel="noopener";cell.append(a);row.append(cell,el("td",f.adapter));table.append(row);}$("modalBody").append(table);$("modal").showModal();}catch(e){failure(e);}};
$("copies").onclick=async()=>{if(!state.file)return;try{const data=await api("copies",{id:state.file.id});$("modalTitle").textContent=`Byte-identical copies (${data.copies.length}; maximum 200 shown)`;$("modalBody").replaceChildren(el("p","Copies are not merged. Resolution prefers local scope and path proximity; equal-content alternatives remain inspectable."));for(const f of data.copies){const b=targetButton(f);b.textContent=f.view+" · "+f.level+" · "+f.path;b.onclick=()=>{$("modal").close();selectFile(f.id).catch(failure);};$("modalBody").append(b);}$("modal").showModal();}catch(e){failure(e);}};
for(const button of document.querySelectorAll("[data-example]"))button.onclick=()=>{const samples={dialogue:["bargainbin","eps_bin_brt8.alb"],bindings:["loc","npc_bunny.acs.PS3"],scene:["loc",".dat.simgroup"]};const [level,query]=samples[button.dataset.example];$("level").value=level;$("view").value="member";$("format").value="";$("search").value=query;listFiles().then(()=>{const first=$("fileList").querySelector("button");if(first)first.click();}).catch(failure);};
async function boot(){const data=await api("summary");$("stats").textContent=`${data.files.toLocaleString()} files / members · ${data.identifiers.toLocaleString()} ID observations`;
  for(const level of data.levels){const option=el("option",(data.level_labels[level.level]||level.level)+` (${level.count.toLocaleString()})`);option.value=level.level;$("level").append(option);}
  if(data.levels.some(l=>l.level==="loc"))$("level").value="loc";
  for(const format of data.formats){const option=el("option",format.format+` (${format.count.toLocaleString()})`);option.value=format.format;$("format").append(option);}
  await listFiles();status(`Index built ${data.built_at} · rebuild after changing input files · nearest-copy policy is not observed runtime loading`);
}
boot().catch(failure);
