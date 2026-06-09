/* YSE Quotation Manager — script.js v5 (GST + Column Box + Initial + Product Type) */

let currentUser=null, products=[], productMap={};
let currentQuotId=null, currentQuotNo=null;
let editMode=false, editQuotId=null, editingPid=null;
let waTab=null;
let currentTheme=localStorage.getItem('yse-theme')||'dark';

const CGST=0.09, SGST=0.09;

window.addEventListener('DOMContentLoaded',async()=>{
  applyTheme(currentTheme,false);
  try{
    const r=await fetch('/api/me'); const d=await r.json();
    if(d.ok){currentUser=d.user; enterApp();}
    else showScreen('loginScreen');
  }catch(e){showScreen('loginScreen');}
});
if('serviceWorker' in navigator) window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));

function toggleTheme(){
  currentTheme=currentTheme==='dark'?'light':'dark';
  localStorage.setItem('yse-theme',currentTheme);
  applyTheme(currentTheme,true);
}
function applyTheme(t,anim){
  if(anim) document.documentElement.style.transition='background .35s,color .25s';
  document.documentElement.setAttribute('data-theme',t);
  ['themeIcon','themeIconLogin','themeIconAdmin'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.textContent=t==='dark'?'☀️':'🌙';
  });
  const mc=document.getElementById('themeColorMeta');
  if(mc) mc.content=t==='dark'?'#0d1117':'#f0f4ff';
}
function togglePassword(id,btn){
  const el=document.getElementById(id); if(!el) return;
  el.type=el.type==='password'?'text':'password';
  btn.textContent=el.type==='password'?'👁':'🙈';
}

/* ── LOGIN ── */
async function doLogin(){
  const email=document.getElementById('loginEmail').value.trim().toLowerCase();
  const pwd=document.getElementById('loginPassword').value.trim();
  const errEl=document.getElementById('loginError');
  const btn=document.getElementById('loginBtn');
  errEl.textContent='';
  if(!email){errEl.textContent='Please enter your email.';return;}
  if(!pwd){errEl.textContent='Please enter your password.';return;}
  btn.disabled=true; btn.textContent='Logging in…';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pwd})});
    const d=await r.json();
    if(d.ok){currentUser=d.user; document.getElementById('loginPassword').value=''; enterApp();}
    else errEl.textContent=d.msg||'Login failed.';
  }catch(e){errEl.textContent='Network error. Try again.';}
  btn.disabled=false; btn.textContent='Login →';
}
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&document.getElementById('loginScreen')&&!document.getElementById('loginScreen').classList.contains('hidden')) doLogin();});

/* ── ENTER APP ── */
async function enterApp(){
  await loadProducts();
  if(currentUser.role==='admin'){
    document.getElementById('adminNameDisplay').textContent=currentUser.name;
    showScreen('adminScreen');
    switchAdminTab('quotations');
    loadAdminQuotations(); loadEmployees();
  }else{
    document.getElementById('userNameDisplay').textContent=currentUser.name;
    showScreen('appScreen');
    switchTab('new');
    addItemRow();
  }
}
async function logout(){
  if(!confirm('Log out?')) return;
  await fetch('/api/logout',{method:'POST'});
  currentUser=null; products=[]; productMap={};
  document.getElementById('loginEmail').value=''; document.getElementById('loginPassword').value=''; document.getElementById('loginError').textContent='';
  cancelEdit(); showScreen('loginScreen');
}

/* ── TABS ── */
function switchTab(tab){
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  const tb=document.getElementById('tab-'+tab); if(tb) tb.classList.add('active');
  document.querySelectorAll('#appScreen .tab-panel').forEach(p=>p.classList.add('hidden'));
  const panel=document.getElementById('panel-'+tab); if(panel) panel.classList.remove('hidden');
  if(tab==='history') loadHistory();
  if(tab==='settings') loadSettingsPanel();
}
function switchAdminTab(tab){
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  const tb=document.getElementById('atab-'+tab); if(tb) tb.classList.add('active');
  document.querySelectorAll('#adminScreen .tab-panel').forEach(p=>p.classList.add('hidden'));
  const panel=document.getElementById('panel-'+tab); if(panel) panel.classList.remove('hidden');
  if(tab==='asettings') loadAdminSettings();
  if(tab==='employees') loadEmployees();
  if(tab==='quotations') loadAdminQuotations();
}

/* ── PRODUCTS ── */
async function loadProducts(){
  try{
    const r=await fetch('/api/products'); products=await r.json();
    productMap={};
    products.forEach(p=>{ if(!productMap[p.name]) productMap[p.name]=[]; productMap[p.name].push(p); });
  }catch(e){ products=[]; productMap={}; }
}
function uniqueNames(){ return [...new Set(products.map(p=>p.name))].sort(); }

/* ── ITEM ROWS ── */
let rowId=0;

// Build map: name -> [product_types]
function uniqueTypesByName(name){ return [...new Set((productMap[name]||[]).map(p=>p.product_type))].filter(Boolean); }
// Build map: name+type -> [sizes]
function variantsByNameType(name,ptype){ return (productMap[name]||[]).filter(p=>p.product_type===ptype); }

function addItemRow(item=null){
  rowId++;
  const rid=rowId;
  const tbody=document.getElementById('itemsBody');
  const tr=document.createElement('tr'); tr.id=`row-${rid}`;
  tr.setAttribute('data-lrate',item?.loading_rate??0);
  tr.setAttribute('data-initial','0');

  let nameOpts=`<option value="">— Product —</option>`;
  uniqueNames().forEach(n=>{
    nameOpts+=`<option value="${esc(n)}"${n===item?.name?' selected':''}>${esc(n)}</option>`;
  });

  tr.innerHTML=`
    <td style="min-width:190px">
      <select id="pname-${rid}" onchange="onNameSelect(${rid},this)" style="width:100%;margin-bottom:3px">${nameOpts}</select>
      <select id="pptype-${rid}" onchange="onPtypeSelect(${rid},this)" style="width:100%;margin-bottom:3px;font-size:11px;display:none">
        <option value="">— Type —</option>
      </select>
      <select id="psize-${rid}" onchange="onSizeSelect(${rid},this)" style="width:100%;font-size:11px;display:none">
        <option value="">— Size —</option>
      </select>
    </td>
    <td><select id="pcalc-${rid}" onchange="calcRow(${rid})" style="font-size:11px">
      <option value="A"${(!item||item.calc_type==='A')?' selected':''}>A</option>
      <option value="B"${item?.calc_type==='B'?' selected':''}>B</option>
    </select></td>
    <td><input type="number" id="qty-${rid}" value="${item?.qty??''}" placeholder="0" min="0" oninput="calcRow(${rid})"/></td>
    <td><input type="number" id="rate-${rid}" value="${item?.rate??''}" placeholder="0" min="0" oninput="calcRow(${rid})"/></td>
    <td><input type="number" id="wt-${rid}" value="${item?.weight??''}" placeholder="0" min="0" oninput="calcRow(${rid})"/></td>
    <td class="row-total" id="total-${rid}">Rs.0</td>
    <td><button class="del-row-btn" onclick="delRow(${rid})">✕</button></td>`;
  tbody.appendChild(tr);

  // Restore selections when editing
  if(item?.name){
    const nameSel=document.getElementById(`pname-${rid}`);
    if(nameSel) nameSel.value=item.name;
    populateTypes(rid, item.name, item.product_type||'', item.size||'');
  }
  if(item) calcRow(rid);
}

function populateTypes(rid, name, selType='', selSize=''){
  const ptSel=document.getElementById(`pptype-${rid}`);
  const szSel=document.getElementById(`psize-${rid}`);
  if(!ptSel||!szSel) return;
  const types=uniqueTypesByName(name);
  if(types.length===0){
    // No types — go straight to sizes
    ptSel.style.display='none';
    populateSizesDirect(rid, name, '', selSize);
  } else if(types.length===1){
    // Only one type — auto-select and hide
    ptSel.style.display='none';
    populateSizesDirect(rid, name, types[0], selSize);
    const tr=document.getElementById(`row-${rid}`);
    if(tr) tr.setAttribute('data-ptype', types[0]);
  } else {
    // Show type dropdown
    ptSel.innerHTML=`<option value="">— Type —</option>`;
    types.forEach(t=>{
      ptSel.innerHTML+=`<option value="${esc(t)}"${t===selType?' selected':''}>${esc(t)}</option>`;
    });
    ptSel.style.display='block';
    if(selType){ populateSizesDirect(rid, name, selType, selSize); }
    else { szSel.style.display='none'; }
  }
}

function populateSizesDirect(rid, name, ptype, selSize=''){
  const szSel=document.getElementById(`psize-${rid}`);
  if(!szSel) return;
  const variants = ptype ? variantsByNameType(name,ptype) : (productMap[name]||[]);
  const sizes=[...new Set(variants.map(v=>v.size))].filter(Boolean);
  if(sizes.length===0){
    szSel.style.display='none';
    // Auto-fill from first variant
    if(variants.length>0) applyVariant(rid, variants[0]);
    return;
  }
  szSel.innerHTML=`<option value="">— Size —</option>`;
  variants.forEach(v=>{
    szSel.innerHTML+=`<option value="${esc(v.size)}"
      data-rate="${v.default_rate}" data-wt="${v.default_weight}"
      data-calc="${v.calc_type}" data-lrate="${v.loading_rate||0}"
      data-spec="${esc(v.specification||'')}" data-ptype="${esc(v.product_type||'')}"
      data-unit="${esc(v.unit||'Nos')}" data-ppu="${v.pieces_per_unit||1}"
      ${v.size===selSize?'selected':''}>${esc(v.size||'Standard')}</option>`;
  });
  szSel.style.display='block';
  if(sizes.length===1 && !selSize){ szSel.selectedIndex=1; onSizeSelect(rid,szSel); }
  else if(selSize){
    // Trigger auto-fill for the pre-selected size
    onSizeSelect(rid, szSel);
  }
}

function applyVariant(rid, v){
  document.getElementById(`rate-${rid}`).value = v.default_rate||0;
  document.getElementById(`wt-${rid}`).value   = v.default_weight||0;
  document.getElementById(`pcalc-${rid}`).value = v.calc_type||'A';
  const tr=document.getElementById(`row-${rid}`);
  if(tr){
    tr.setAttribute('data-lrate', v.loading_rate||0);
    tr.setAttribute('data-spec',  v.specification||'');
    tr.setAttribute('data-ptype', v.product_type||'');
    tr.setAttribute('data-unit',  v.unit||'Nos');
    tr.setAttribute('data-ppu',   v.pieces_per_unit||1);
  }
  calcRow(rid);
}

function onNameSelect(rid,sel){
  if(!sel.value){ calcRow(rid); return; }
  const ptSel=document.getElementById(`pptype-${rid}`);
  const szSel=document.getElementById(`psize-${rid}`);
  if(ptSel) ptSel.style.display='none';
  if(szSel) szSel.style.display='none';
  document.getElementById(`rate-${rid}`).value='';
  document.getElementById(`wt-${rid}`).value='';
  populateTypes(rid, sel.value, '', '');
  calcRow(rid);
}
function onPtypeSelect(rid,sel){
  const nameSel=document.getElementById(`pname-${rid}`);
  if(!nameSel||!sel.value) return;
  const tr=document.getElementById(`row-${rid}`);
  if(tr) tr.setAttribute('data-ptype', sel.value);
  document.getElementById(`rate-${rid}`).value='';
  document.getElementById(`wt-${rid}`).value='';
  populateSizesDirect(rid, nameSel.value, sel.value, '');
  calcRow(rid);
}
function onSizeSelect(rid,sel){
  const opt=sel.options[sel.selectedIndex];
  if(!opt||!opt.value) return;
  document.getElementById(`rate-${rid}`).value  = opt.dataset.rate||0;
  document.getElementById(`wt-${rid}`).value    = opt.dataset.wt||0;
  document.getElementById(`pcalc-${rid}`).value = opt.dataset.calc||'A';
  const tr=document.getElementById(`row-${rid}`);
  if(tr){
    tr.setAttribute('data-lrate', opt.dataset.lrate||0);
    tr.setAttribute('data-spec',  opt.dataset.spec||'');
    tr.setAttribute('data-ptype', opt.dataset.ptype||'');
    tr.setAttribute('data-unit',  opt.dataset.unit||'Nos');
    tr.setAttribute('data-ppu',   opt.dataset.ppu||1);
  }
  calcRow(rid);
}

function calcRow(rid){
  const qty=parseFloat(document.getElementById(`qty-${rid}`)?.value)||0;
  const rate=parseFloat(document.getElementById(`rate-${rid}`)?.value)||0;
  const wt=parseFloat(document.getElementById(`wt-${rid}`)?.value)||0;
  const type=document.getElementById(`pcalc-${rid}`)?.value||'A';
  const tr=document.getElementById(`row-${rid}`);
  const unit=tr?.getAttribute('data-unit')||'Nos';
  const ppu=parseFloat(tr?.getAttribute('data-ppu')||'1');
  const effectiveQty=(unit==='Set'&&ppu>1)?qty*ppu:qty;
  const total=type==='B'?effectiveQty*rate*wt:effectiveQty*rate;
  const el=document.getElementById(`total-${rid}`);
  if(el) el.textContent=`Rs.${fmtN(total)}`;
  recalcAll();
}
function delRow(rid){ document.getElementById(`row-${rid}`)?.remove(); recalcAll(); }
/* ── MACHINE PRINT / INITIAL — separate fixed row ── */
function addMachinePrint(){
  // Check if already added
  const existing = document.getElementById('mp-row');
  if(existing){ existing.querySelector('input[type=number]').focus(); return; }

  const tbody = document.getElementById('itemsBody');
  const tr = document.createElement('tr');
  tr.id = 'mp-row';
  tr.setAttribute('data-initial','1');
  tr.setAttribute('data-lrate','0');
  tr.setAttribute('data-spec','Machine Printing / Initial');
  tr.setAttribute('data-ptype','Machine Printing');
  tr.innerHTML = `
    <td colspan="2" style="font-weight:600;color:#92400e;font-size:13px">
      🖨️ Machine Print / Initial &nbsp;<small style="font-weight:400;color:var(--ink-muted)">(1 letter = Rs.5)</small>
      <div style="margin-top:4px"><input type="text" id="mp-note" placeholder="Note / description (shown in PDF)" style="font-weight:400;font-size:12px;width:100%;color:var(--ink);border:1px solid var(--border);border-radius:4px;padding:3px 6px;"/></div>
    </td>
    <td><input type="number" id="mp-qty" value="" placeholder="No. of letters" min="0" oninput="calcMachinePrint()"/></td>
    <td style="color:var(--ink-muted);font-size:12px">Rs.5 / letter</td>
    <td style="color:var(--ink-muted)">—</td>
    <td class="row-total"><input type="number" id="mp-total-input" value="0" min="0" step="0.01" style="width:90px;text-align:right;font-weight:600;color:var(--ink);" oninput="recalcAll()" title="You can edit this total manually"/></td>
    <td><button class="del-row-btn" onclick="removeMachinePrint()">✕</button></td>`;
  tbody.appendChild(tr);
  document.getElementById('mp-qty').focus();
  document.getElementById('mp-qty').addEventListener('input', calcMachinePrint);
}
function removeMachinePrint(){
  document.getElementById('mp-row')?.remove();
  recalcAll();
}
function calcMachinePrint(){
  const qty = parseFloat(document.getElementById('mp-qty')?.value)||0;
  const autoTotal = qty * 5;
  const totalInput = document.getElementById('mp-total-input');
  if(totalInput) totalInput.value = autoTotal.toFixed(2);
  recalcAll();
}

function recalcAll(){
  const tbody=document.getElementById('itemsBody'); if(!tbody) return;
  let taxSub=0, initialSub=0, totalWt=0, autoLoading=0;

  tbody.querySelectorAll('tr').forEach(tr=>{
    const rid=tr.id.replace('row-','');
    const qty=parseFloat(document.getElementById(`qty-${rid}`)?.value)||0;
    const rate=parseFloat(document.getElementById(`rate-${rid}`)?.value)||0;
    const wt=parseFloat(document.getElementById(`wt-${rid}`)?.value)||0;
    const type=document.getElementById(`pcalc-${rid}`)?.value||'A';
    const lrate=parseFloat(tr.getAttribute('data-lrate')||'0');
    const unit=tr.getAttribute('data-unit')||'Nos';
    const ppu=parseFloat(tr.getAttribute('data-ppu')||'1');
    const isInit=tr.getAttribute('data-initial')==='1';
    // For Set type: convert sets to pieces for calculation
    const effectiveQty = (unit==='Set' && ppu>1) ? qty*ppu : qty;
    const total=type==='B'?effectiveQty*rate*wt:qty*rate;
    totalWt+=effectiveQty*wt;
    if(isInit) initialSub+=total;
    else{
      taxSub+=total;
      if(type==='B') autoLoading+=effectiveQty*wt*lrate;
      else autoLoading+=qty*lrate;
    }
  });

  // Also count machine print row
  const mpTotalInput = document.getElementById('mp-total-input');
  const mpTotal = parseFloat(mpTotalInput?.value)||0;
  if(document.getElementById('mp-row')) initialSub += mpTotal;

  const lcEl=document.getElementById('loadingCharges');
  if(!lcEl.getAttribute('data-manual')) lcEl.value=Math.round(autoLoading);
  const lc=parseFloat(lcEl.value)||0;

  const cgst=Math.round(taxSub*CGST*100)/100;
  const sgst=Math.round(taxSub*SGST*100)/100;
  const grand=taxSub+initialSub+lc+cgst+sgst;

  document.getElementById('totalWeight').textContent=`${totalWt.toFixed(1)} kg`;
  document.getElementById('taxableSubtotal').textContent=`Rs.${fmtN(taxSub)}`;
  document.getElementById('initialChargesDisplay').textContent=initialSub>0?`Rs.${fmtN(initialSub)}`:'—';
  document.getElementById('cgstDisplay').textContent=`Rs.${fmtN(cgst)} (9%)`;
  document.getElementById('sgstDisplay').textContent=`Rs.${fmtN(sgst)} (9%)`;
  document.getElementById('grandTotal').textContent=`Rs.${fmtN(grand)}`;

  // Store computed values for save
  document.getElementById('hiddenTaxSub').value=taxSub;
  document.getElementById('hiddenInitial').value=initialSub;
  document.getElementById('hiddenCgst').value=cgst;
  document.getElementById('hiddenSgst').value=sgst;
}

function manualLoadingUpdate(){
  document.getElementById('loadingCharges').setAttribute('data-manual','true');
  recalcAll();
}

/* ── GENERATE QUOTATION ── */
async function generateQuotation(){
  const custName=document.getElementById('custName').value.trim();
  const custLoc=document.getElementById('custLocation').value.trim();
  const custPhone=document.getElementById('custPhone').value.trim();
  const errEl=document.getElementById('quotError');
  errEl.textContent=''; errEl.style.color='var(--red)';
  if(!custName){errEl.textContent='Please enter customer name.';return;}
  if(!custLoc){errEl.textContent='Please enter customer location.';return;}
  if(!custPhone){errEl.textContent='Please enter customer phone.';return;}

  const tbody=document.getElementById('itemsBody');
  const items=[]; let totalWt=0, taxSub=0, initSub=0;

  tbody.querySelectorAll('tr').forEach(tr=>{
    const rid=tr.id.replace('row-','');
    const name=document.getElementById(`pname-${rid}`)?.value;
    if(!name) return;
    const size=document.getElementById(`psize-${rid}`)?.value||'';
    const spec=tr.getAttribute('data-spec')||'';
    const ptype=tr.getAttribute('data-ptype')||'';
    const isInit=tr.getAttribute('data-initial')==='1';
    const qty=parseFloat(document.getElementById(`qty-${rid}`)?.value)||0;
    const rate=parseFloat(document.getElementById(`rate-${rid}`)?.value)||0;
    const wt=parseFloat(document.getElementById(`wt-${rid}`)?.value)||0;
    const type=document.getElementById(`pcalc-${rid}`)?.value||'A';
    const lrate=parseFloat(tr.getAttribute('data-lrate')||'0');
    const unit=tr.getAttribute('data-unit')||'Nos';
    const ppu=parseFloat(tr.getAttribute('data-ppu')||'1');
    const effectiveQty=(unit==='Set'&&ppu>1)?qty*ppu:qty;
    const total=type==='B'?effectiveQty*rate*wt:qty*rate;
    totalWt+=effectiveQty*wt;
    if(isInit) initSub+=total; else taxSub+=total;
    items.push({name,size,specification:spec,product_type:ptype,qty,rate,weight:wt,
      calc_type:type,loading_rate:lrate,total,is_initial:isInit,unit,pieces_per_unit:ppu,effective_qty:effectiveQty});
  });

  // Add machine print row if present
  const mpQty2=parseFloat(document.getElementById('mp-qty')?.value)||0;
  if(mpQty2>0 || document.getElementById('mp-row')){
    const mpTotalVal=parseFloat(document.getElementById('mp-total-input')?.value)||0;
    const mpNote=document.getElementById('mp-note')?.value||'';
    if(mpTotalVal>0 || mpQty2>0){
      const mpTotal2=mpTotalVal>0?mpTotalVal:(mpQty2*5);
      initSub+=mpTotal2;
      items.push({name:'Machine Print / Initial',size:'',specification:'Machine Printing / Initial – 1 letter = Rs.5',
        product_type:'Machine Printing',qty:mpQty2,rate:5,weight:0,calc_type:'A',loading_rate:0,total:mpTotal2,is_initial:true,mp_note:mpNote});
    }
  }
  if(!items.length){errEl.textContent='Please add at least one product.';return;}

  const lc=parseFloat(document.getElementById('loadingCharges').value)||0;
  const cgst=parseFloat(document.getElementById('hiddenCgst').value)||Math.round(taxSub*CGST*100)/100;
  const sgst=parseFloat(document.getElementById('hiddenSgst').value)||Math.round(taxSub*SGST*100)/100;
  const grand=taxSub+initSub+lc+cgst+sgst;

  const url=editMode?`/api/quotations/${editQuotId}`:'/api/quotations';
  const method=editMode?'PUT':'POST';
  try{
    const r=await fetch(url,{method,headers:{'Content-Type':'application/json'},
      body:JSON.stringify({customer_name:custName,customer_location:custLoc,customer_phone:custPhone,
        items,loading_charges:lc,initial_charges:initSub,taxable_subtotal:taxSub,
        cgst_amount:cgst,sgst_amount:sgst,grand_total:grand,total_weight:totalWt})});
    const d=await r.json();
    if(d.ok){
      currentQuotId=editMode?editQuotId:d.id;
      currentQuotNo=d.quot_no||currentQuotNo;
      if(editMode){
        errEl.style.color='var(--green)';
        errEl.textContent='✅ Quotation updated successfully!';
        setTimeout(()=>{errEl.textContent='';errEl.style.color='var(--red)';},3000);
        document.getElementById('editActionBtns').classList.remove('hidden');
      }else{
        document.getElementById('modalQuotNo').textContent=`Quotation No: ${currentQuotNo}`;
        document.getElementById('pdfModal').classList.remove('hidden');
      }
    }else{errEl.textContent='Failed to save quotation.';}
  }catch(e){errEl.textContent='Network error.';}
}

/* ── EDIT QUOTATION ── */
async function editQuotation(qid){
  try{
    const r=await fetch('/api/quotations'); const list=await r.json();
    const q=list.find(x=>x.id===qid); if(!q) return;
    const itemsList=typeof q.items==='string'?JSON.parse(q.items):q.items;
    switchTab('new');
    editMode=true; editQuotId=qid; currentQuotNo=q.quot_no;
    document.getElementById('custName').value=q.customer_name||'';
    document.getElementById('custLocation').value=q.customer_location||'';
    document.getElementById('custPhone').value=q.customer_phone||'';
    document.getElementById('itemsBody').innerHTML=''; rowId=0;
    document.getElementById('mp-row')?.remove();
    const regularItems=itemsList.filter(it=>!it.is_initial);
    const mpItem=itemsList.find(it=>it.is_initial);
    regularItems.forEach(it=>addItemRow(it));
    if(mpItem){ addMachinePrint(); const mpQEl=document.getElementById('mp-qty'); if(mpQEl) mpQEl.value=mpItem.qty; const mpTEl=document.getElementById('mp-total-input'); if(mpTEl) mpTEl.value=(mpItem.total||mpItem.qty*5).toFixed(2); const mpNEl=document.getElementById('mp-note'); if(mpNEl) mpNEl.value=mpItem.mp_note||''; calcMachinePrint(); }
    document.getElementById('loadingCharges').value=q.loading_charges||0;
    document.getElementById('loadingCharges').setAttribute('data-manual','true');
    recalcAll();
    const btn=document.getElementById('generateBtn'); if(btn) btn.textContent='🔄 Update Quotation';
    const title=document.getElementById('formTitle'); if(title) title.textContent=`Edit — ${q.quot_no}`;
    document.getElementById('cancelEditBtn').classList.remove('hidden');
    document.getElementById('editActionBtns').classList.add('hidden');
  }catch(e){alert('Failed to load quotation.');}
}

function cancelEdit(){
  document.getElementById('loadingCharges')?.removeAttribute('data-manual');
  editMode=false; editQuotId=null; currentQuotNo=null;
  ['custName','custLocation','custPhone'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
  const ib=document.getElementById('itemsBody'); if(ib){ib.innerHTML='';rowId=0;addItemRow();recalcAll();}
  const btn=document.getElementById('generateBtn'); if(btn) btn.textContent='📄 Generate Quotation';
  const title=document.getElementById('formTitle'); if(title) title.textContent='Products';
  document.getElementById('cancelEditBtn')?.classList.add('hidden');
  document.getElementById('editActionBtns')?.classList.add('hidden');
  const errEl=document.getElementById('quotError'); if(errEl){errEl.textContent='';errEl.style.color='var(--red)';}
}

/* ── DELETE ── */
async function deleteQuotation(qid){
  if(!confirm('Delete this quotation?')) return;
  try{const r=await fetch(`/api/quotations/${qid}`,{method:'DELETE'});const d=await r.json();if(d.ok)loadHistory();}catch(e){}
}
async function adminDeleteQuotation(qid){
  if(!confirm('Delete this quotation?')) return;
  try{const r=await fetch(`/api/quotations/${qid}`,{method:'DELETE'});const d=await r.json();if(d.ok)loadAdminQuotations();}catch(e){}
}

/* ── PDF & WHATSAPP ── */
function downloadPDF(){ if(currentQuotId) window.open(`/api/quotations/${currentQuotId}/pdf`,'_blank'); }
function shareWhatsApp(){ if(currentQuotId) openWA(`${location.origin}/api/quotations/${currentQuotId}/pdf`); }
function waShare(qid){ openWA(`${location.origin}/api/quotations/${qid}/pdf`); }
function openWA(url){
  const txt=encodeURIComponent(url);
  const mob=/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if(mob){ window.location.href=`whatsapp://send?text=${txt}`; }
  else{
    window.location.href=`whatsapp://send?text=${txt}`;
    setTimeout(()=>{
      if(waTab&&!waTab.closed) waTab.location.href=`https://web.whatsapp.com/send?text=${txt}`;
      else waTab=window.open(`https://web.whatsapp.com/send?text=${txt}`,'_wa');
    },2000);
  }
}
function closeModal(){ document.getElementById('pdfModal').classList.add('hidden'); cancelEdit(); }

/* ── HISTORY ── */
let allHistory=[], allAdminQ=[];
async function loadHistory(){
  try{const r=await fetch('/api/quotations');const d=await r.json();allHistory=Array.isArray(d)?d:[];renderHistory(allHistory);}
  catch(e){renderHistory([]);}
}
function filterHistory(){
  const q=(document.getElementById('historySearch')?.value||'').toLowerCase();
  renderHistory(!q?allHistory:allHistory.filter(x=>[x.customer_name,x.customer_location,x.customer_phone,x.quot_no].some(f=>(f||'').toLowerCase().includes(q))));
}
function renderHistory(list){
  const con=document.getElementById('historyList'); const emp=document.getElementById('historyEmpty');
  con.innerHTML='';
  if(!list.length){emp.style.display='flex';return;} emp.style.display='none';
  list.forEach(q=>{
    const date=q.created_at?new Date(q.created_at.toString()).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'';
    const d=document.createElement('div'); d.className='hist-item';
    d.innerHTML=`<div class="hist-info">
      <div class="hist-no">${esc(q.quot_no)}</div>
      <div class="hist-customer">${esc(q.customer_name)}, ${esc(q.customer_location)}</div>
      <div class="hist-meta">📞 ${esc(q.customer_phone)} · 📅 ${date}</div>
    </div>
    <div class="hist-actions">
      <div class="hist-amount">Rs.${fmtN(q.grand_total)}</div>
      <div class="hist-btns-row">
        <button class="hist-btn" onclick="window.open('/api/quotations/${q.id}/pdf','_blank')">📥 PDF</button>
        <button class="hist-btn wa" onclick="waShare(${q.id})">WA</button>
        <button class="hist-btn edit" onclick="editQuotation(${q.id})">✏️ Edit</button>
        <button class="hist-btn delete" onclick="deleteQuotation(${q.id})">🗑️</button>
      </div>
    </div>`;
    con.appendChild(d);
  });
}

/* ── SETTINGS ── */
async function loadSettingsPanel(){
  const isEmp=currentUser?.role==='employee';
  ['companySettingsCard','productSettingsCard','quotSettingsCard'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.style.display=isEmp?'flex':'none';
  });
  if(isEmp){
    try{const r=await fetch('/api/profile');const p=await r.json();
      document.getElementById('settingContactName').value=p.contact_name||'';
      document.getElementById('settingContactPhone').value=p.contact_phone||'';
      if(document.getElementById('settingDesignation')) document.getElementById('settingDesignation').value=p.designation||'Sales Executive';
    }catch(e){}
    try{
      const [sr,pr]=await Promise.all([fetch('/api/settings'),fetch('/api/products')]);
      const s=await sr.json(); products=await pr.json();
      productMap={}; products.forEach(p=>{if(!productMap[p.name])productMap[p.name]=[];productMap[p.name].push(p);});
      document.getElementById('settingQuotPrefix').value=s.quot_prefix||'YSE/QT';
      document.getElementById('settingQuotCounter').value=s.quot_counter||'100';
      updateNextQuotPreview();
      renderProductsList('productsList');
    }catch(e){}
  }
}
async function saveProfile(){
  const name=document.getElementById('settingContactName').value.trim();
  const phone=document.getElementById('settingContactPhone').value.trim();
  const desig=document.getElementById('settingDesignation')?.value||'Sales Executive';
  const el=document.getElementById('profileSuccess');
  try{const r=await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contact_name:name,contact_phone:phone,designation:desig})});
    const d=await r.json(); if(d.ok){el.textContent='✅ Saved!';setTimeout(()=>el.textContent='',2500);}
  }catch(e){}
}
function updateNextQuotPreview(){
  const p=document.getElementById('settingQuotPrefix')?.value||'YSE/QT';
  const c=parseInt(document.getElementById('settingQuotCounter')?.value||'100')+1;
  const el=document.getElementById('nextQuotPreview'); if(el) el.textContent=`${p}/${c}`;
}
async function saveSettings(){
  const p=document.getElementById('settingQuotPrefix').value.trim();
  const c=document.getElementById('settingQuotCounter').value.trim();
  const el=document.getElementById('settingsSuccess');
  try{const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quot_prefix:p,quot_counter:c})});
    const d=await r.json(); if(d.ok){el.textContent='✅ Saved!';updateNextQuotPreview();setTimeout(()=>el.textContent='',2500);}
  }catch(e){}
}
async function changePassword(){
  const old=document.getElementById('oldPass').value.trim();
  const nw=document.getElementById('newPass').value.trim();
  const cf=document.getElementById('confirmPass').value.trim();
  const err=document.getElementById('passError'); const suc=document.getElementById('passSuccess');
  err.textContent=''; suc.textContent='';
  if(!old||!nw||!cf){err.textContent='Please fill all fields.';return;}
  if(nw!==cf){err.textContent='New passwords do not match.';return;}
  if(nw.length<6){err.textContent='Password must be at least 6 characters.';return;}
  try{const r=await fetch('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:old,new_password:nw})});
    const d=await r.json();
    if(d.ok){suc.textContent='✅ Password changed!';['oldPass','newPass','confirmPass'].forEach(id=>document.getElementById(id).value='');setTimeout(()=>suc.textContent='',3000);}
    else err.textContent=d.msg||'Failed.';
  }catch(e){err.textContent='Network error.';}
}

/* ── PRODUCTS ── */
async function addProduct(){
  const name=document.getElementById('newProdName').value.trim();
  if(!name){alert('Product name required.');return;}
  const d={name,product_type:document.getElementById('newProdPtype').value.trim(),
    size:document.getElementById('newProdSize').value.trim(),
    specification:document.getElementById('newProdSpec').value.trim(),
    default_rate:parseFloat(document.getElementById('newProdRate').value)||0,
    default_weight:parseFloat(document.getElementById('newProdWeight').value)||0,
    calc_type:document.getElementById('newProdType').value,
    loading_rate:parseFloat(document.getElementById('newProdLrate').value)||0,
    is_initial:document.getElementById('newProdIsInitial')?.checked||false,
    unit:document.getElementById('newProdUnit')?.value||'Nos',
    pieces_per_unit:parseInt(document.getElementById('newProdPpu')?.value)||1};
  try{const r=await fetch('/api/products',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const res=await r.json();
    if(res.ok){['newProdName','newProdPtype','newProdSize','newProdSpec','newProdRate','newProdWeight','newProdLrate'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
      await loadProducts(); renderProductsList('productsList');}
  }catch(e){}
}
async function deleteProduct(pid){
  if(!confirm('Remove this product variant?')) return;
  try{await fetch(`/api/products/${pid}`,{method:'DELETE'});await loadProducts();renderProductsList('productsList');renderProductsList('adminProductsList');}catch(e){}
}
function openEditProd(pid){
  const p=products.find(x=>x.id===pid); if(!p) return;
  editingPid=pid;
  document.getElementById('editProdName').value=p.name||'';
  document.getElementById('editProdPtype').value=p.product_type||'';
  document.getElementById('editProdSize').value=p.size||'';
  document.getElementById('editProdSpec').value=p.specification||'';
  document.getElementById('editProdRate').value=p.default_rate||0;
  document.getElementById('editProdWeight').value=p.default_weight||0;
  document.getElementById('editProdType').value=p.calc_type||'A';
  document.getElementById('editProdLrate').value=p.loading_rate||0;
  if(document.getElementById('editProdIsInitial')) document.getElementById('editProdIsInitial').checked=!!p.is_initial;
  if(document.getElementById('editProdUnit')){
    document.getElementById('editProdUnit').value=p.unit||'Nos';
    togglePpuField('editProdPpu', p.unit||'Nos');
  }
  if(document.getElementById('editProdPpu')) document.getElementById('editProdPpu').value=p.pieces_per_unit||1;
  document.getElementById('editProductModal').classList.remove('hidden');
}
function closeEditProd(){document.getElementById('editProductModal').classList.add('hidden');editingPid=null;}
async function saveEditProd(){
  if(!editingPid) return;
  const d={name:document.getElementById('editProdName').value.trim(),
    product_type:document.getElementById('editProdPtype').value.trim(),
    size:document.getElementById('editProdSize').value.trim(),
    specification:document.getElementById('editProdSpec').value.trim(),
    default_rate:parseFloat(document.getElementById('editProdRate').value)||0,
    default_weight:parseFloat(document.getElementById('editProdWeight').value)||0,
    calc_type:document.getElementById('editProdType').value,
    loading_rate:parseFloat(document.getElementById('editProdLrate').value)||0,
    is_initial:document.getElementById('editProdIsInitial')?.checked||false,
    unit:document.getElementById('editProdUnit')?.value||'Nos',
    pieces_per_unit:parseInt(document.getElementById('editProdPpu')?.value)||1};
  if(!d.name){alert('Product name required.');return;}
  try{const r=await fetch(`/api/products/${editingPid}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const res=await r.json();
    if(res.ok){closeEditProd();await loadProducts();renderProductsList('productsList');renderProductsList('adminProductsList');}
  }catch(e){alert('Failed to update.');}
}
function renderProductsList(cid){
  const con=document.getElementById(cid); if(!con) return;
  con.innerHTML='';
  if(!products.length){con.innerHTML='<div class="empty-state"><p>No products yet.</p></div>';return;}
  products.forEach(p=>{
    const d=document.createElement('div'); d.className='product-item';
    d.innerHTML=`<div class="prod-info">
      <div class="prod-name">${esc(p.name)}
        ${p.product_type?`<span class="prod-size-badge">${esc(p.product_type)}</span>`:''}
        ${p.size?`<span class="prod-size-badge" style="background:rgba(16,185,129,.15);color:#065f46">${esc(p.size)}</span>`:''}
        ${p.is_initial?'<span class="prod-size-badge" style="background:rgba(245,158,11,.15);color:#92400e">Initial</span>':''}
      </div>
      ${p.specification?`<div class="prod-spec">${esc(p.specification)}</div>`:''}
      <div class="prod-meta">Rate: Rs.${p.default_rate} · Wt: ${p.default_weight}kg · Loading: Rs.${p.loading_rate||0} · Type ${p.calc_type}</div>
    </div>
    <div class="prod-actions">
      <button class="hist-btn edit" onclick="openEditProd(${p.id})">✏️</button>
      <button class="del-row-btn" onclick="deleteProduct(${p.id})">🗑️</button>
    </div>`;
    con.appendChild(d);
  });
}

/* ── EMPLOYEES ── */
async function loadEmployees(){
  try{const r=await fetch('/api/admin/employees');const list=await r.json();
    renderEmployees(list);
    const sel=document.getElementById('adminEmpFilter');
    if(sel){const cur=sel.value;sel.innerHTML='<option value="">All Employees</option>';
      list.filter(e=>e.role==='employee').forEach(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.name;if(e.id==cur)o.selected=true;sel.appendChild(o);});}
  }catch(e){}
}
function renderEmployees(list){
  const con=document.getElementById('employeesList'); if(!con) return;
  con.innerHTML='';
  if(!list.length){con.innerHTML='<div class="empty-state"><p>No employees.</p></div>';return;}
  list.forEach(e=>{
    const d=document.createElement('div'); d.className='emp-item';
    d.innerHTML=`<div class="emp-info">
      <div class="emp-name">${esc(e.name)} <span class="prod-type ${e.role}">${e.role}</span></div>
      <div class="emp-email">${esc(e.email)}</div>
      ${e.designation?`<div class="emp-email" style="color:var(--ink-muted)">${esc(e.designation)}</div>`:''}
    </div>
    <div class="emp-actions">
      <button class="hist-btn" onclick="promptReset(${e.id},'${esc(e.name)}')">🔑</button>
      ${e.role!=='admin'?`<button class="hist-btn delete" onclick="deleteEmp(${e.id},'${esc(e.name)}')">🗑️</button>`:''}
    </div>`;
    con.appendChild(d);
  });
}
async function addEmployee(){
  const name=document.getElementById('newEmpName').value.trim();
  const email=document.getElementById('newEmpEmail').value.trim().toLowerCase();
  const pwd=document.getElementById('newEmpPass').value.trim();
  const role=document.getElementById('newEmpRole').value;
  const err=document.getElementById('addEmpError'); const suc=document.getElementById('addEmpSuccess');
  err.textContent=''; suc.textContent='';
  if(!name||!email||!pwd){err.textContent='All fields required.';return;}
  try{const r=await fetch('/api/admin/employees',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email,password:pwd,role})});
    const d=await r.json();
    if(d.ok){suc.textContent=`✅ ${name} added!`;['newEmpName','newEmpEmail','newEmpPass'].forEach(id=>document.getElementById(id).value='');setTimeout(()=>suc.textContent='',3000);loadEmployees();}
    else err.textContent=d.msg||'Failed.';
  }catch(e){err.textContent='Network error.';}
}
async function deleteEmp(uid,name){
  if(!confirm(`Delete ${name}?`)) return;
  try{await fetch(`/api/admin/employees/${uid}`,{method:'DELETE'});loadEmployees();}catch(e){}
}
async function promptReset(uid,name){
  const p=prompt(`New password for ${name}:`); if(!p) return;
  if(p.length<6){alert('Min 6 chars.');return;}
  try{const r=await fetch(`/api/admin/employees/${uid}/reset-password`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})});
    const d=await r.json(); if(d.ok) alert(`✅ Reset for ${name}`); else alert('Failed.');
  }catch(e){alert('Network error.');}
}

/* ── ADMIN QUOTATIONS ── */
async function loadAdminQuotations(){
  const uid=document.getElementById('adminEmpFilter')?.value||'';
  const url=uid?`/api/admin/quotations?user_id=${uid}`:'/api/admin/quotations';
  try{const r=await fetch(url);const d=await r.json();allAdminQ=Array.isArray(d)?d:[];renderAdminQ(allAdminQ);}catch(e){renderAdminQ([]);}
}
function filterAdminQuotations(){
  const q=(document.getElementById('adminSearch')?.value||'').toLowerCase();
  renderAdminQ(!q?allAdminQ:allAdminQ.filter(x=>[x.customer_name,x.customer_location,x.customer_phone,x.quot_no,x.created_by_name].some(f=>(f||'').toLowerCase().includes(q))));
}
function renderAdminQ(list){
  const con=document.getElementById('adminQuotList'); const emp=document.getElementById('adminQuotEmpty');
  con.innerHTML='';
  if(!list.length){emp.style.display='flex';return;} emp.style.display='none';
  list.forEach(q=>{
    const date=q.created_at?new Date(q.created_at.toString()).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}):'';
    const d=document.createElement('div'); d.className='hist-item';
    d.innerHTML=`<div class="hist-info">
      <div class="hist-no">${esc(q.quot_no)}</div>
      <div class="hist-customer">${esc(q.customer_name)}, ${esc(q.customer_location)}</div>
      <div class="hist-meta">📞 ${esc(q.customer_phone)} · 📅 ${date} · 👤 ${esc(q.created_by_name||'')}</div>
    </div>
    <div class="hist-actions">
      <div class="hist-amount">Rs.${fmtN(q.grand_total)}</div>
      <div class="hist-btns-row">
        <button class="hist-btn" onclick="window.open('/api/quotations/${q.id}/pdf','_blank')">📥 PDF</button>
        <button class="hist-btn wa" onclick="waShare(${q.id})">WA</button>
        <button class="hist-btn delete" onclick="adminDeleteQuotation(${q.id})">🗑️</button>
      </div>
    </div>`;
    con.appendChild(d);
  });
}

/* ── ADMIN SETTINGS ── */
async function loadAdminSettings(){
  try{
    const [sr,pr]=await Promise.all([fetch('/api/settings'),fetch('/api/products')]);
    const s=await sr.json(); products=await pr.json();
    productMap={}; products.forEach(p=>{if(!productMap[p.name])productMap[p.name]=[];productMap[p.name].push(p);});
    document.getElementById('aSettingQuotPrefix').value=s.quot_prefix||'YSE/QT';
    document.getElementById('aSettingQuotCounter').value=s.quot_counter||'100';
    updateAdminNextQuot(); renderProductsList('adminProductsList');
  }catch(e){}
}
function updateAdminNextQuot(){
  const p=document.getElementById('aSettingQuotPrefix')?.value||'YSE/QT';
  const c=parseInt(document.getElementById('aSettingQuotCounter')?.value||'100')+1;
  const el=document.getElementById('adminNextQuotPreview'); if(el) el.textContent=`${p}/${c}`;
}
async function saveAdminSettings(){
  const p=document.getElementById('aSettingQuotPrefix').value.trim();
  const c=document.getElementById('aSettingQuotCounter').value.trim();
  const el=document.getElementById('aSettingsSuccess');
  try{const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quot_prefix:p,quot_counter:c})});
    const d=await r.json(); if(d.ok){el.textContent='✅ Saved!';updateAdminNextQuot();setTimeout(()=>el.textContent='',2500);}
  }catch(e){}
}
async function addAdminProduct(){
  const name=document.getElementById('aProdName').value.trim();
  if(!name){alert('Product name required.');return;}
  const d={name,product_type:document.getElementById('aProdPtype').value.trim(),
    size:document.getElementById('aProdSize').value.trim(),
    specification:document.getElementById('aProdSpec').value.trim(),
    default_rate:parseFloat(document.getElementById('aProdRate').value)||0,
    default_weight:parseFloat(document.getElementById('aProdWeight').value)||0,
    calc_type:document.getElementById('aProdType').value,
    loading_rate:parseFloat(document.getElementById('aProdLrate').value)||0,
    is_initial:document.getElementById('aProdIsInitial')?.checked||false};
  try{const r=await fetch('/api/products',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const res=await r.json();
    if(res.ok){['aProdName','aProdPtype','aProdSize','aProdSpec','aProdRate','aProdWeight','aProdLrate'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});
      await loadProducts();renderProductsList('adminProductsList');}
  }catch(e){}
}
async function adminChangePassword(){
  const old=document.getElementById('adminOldPass').value.trim();
  const nw=document.getElementById('adminNewPass').value.trim();
  const cf=document.getElementById('adminConfirmPass').value.trim();
  const err=document.getElementById('adminPassError'); const suc=document.getElementById('adminPassSuccess');
  err.textContent=''; suc.textContent='';
  if(!old||!nw||!cf){err.textContent='Please fill all fields.';return;}
  if(nw!==cf){err.textContent='New passwords do not match.';return;}
  if(nw.length<6){err.textContent='Min 6 chars.';return;}
  try{const r=await fetch('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:old,new_password:nw})});
    const d=await r.json();
    if(d.ok){suc.textContent='✅ Changed!';['adminOldPass','adminNewPass','adminConfirmPass'].forEach(id=>document.getElementById(id).value='');setTimeout(()=>suc.textContent='',3000);}
    else err.textContent=d.msg||'Failed.';
  }catch(e){err.textContent='Network error.';}
}

/* ── HELPERS ── */
function fmtN(n){
  const x=Math.round(Number(n));
  const s=String(x);
  if(s.length<=3) return s;
  const last3=s.slice(-3);
  let rest=s.slice(0,-3);
  const parts=[];
  while(rest.length>2){ parts.unshift(rest.slice(-2)); rest=rest.slice(0,-2); }
  if(rest) parts.unshift(rest);
  return parts.join(",")+","+last3;
}
function togglePpuField(inputId, unit){
  const wrap=document.getElementById(inputId+'Wrap');
  if(wrap) wrap.style.display=(unit==='Set')?'block':'none';
}
function esc(s){ const d=document.createElement('div');d.appendChild(document.createTextNode(String(s||'')));return d.innerHTML; }
function showScreen(id){ document.querySelectorAll('.screen').forEach(s=>s.classList.add('hidden'));document.getElementById(id).classList.remove('hidden'); }
