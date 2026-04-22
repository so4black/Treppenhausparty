import json
from pathlib import Path
from datetime import datetime

import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit.errors import StreamlitSecretNotFoundError

SPREADSHEET_ID = "1z6pVOSBNUcrWAdmgQfuqfNpvlwBYUkPmd58Xu29kj-U"
SHEET_NAME = "Backend_Kasse"
HEADER = ["ID", "Zeitstempel", "Produkte", "Anzahl_Gesamt",
          "Betrag_Gesamt", "Erhalten", "Rueckgeld", "Rabatt", "Kassierer"]

SERVICE_ACCOUNT_CANDIDATES = [
    Path("service_account.json"),
    Path(".streamlit/service_account.json"),
    Path(".streamlit/secrets.toml.txt"),
    Path(r"C:\Users\leul.zewdie\Downloads\party-dashboard-491808-a0ddf9a20e45.json"),
]

KASSE_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{height:100%;overflow:auto;margin:0}
body{font-family:sans-serif;padding:12px;background:#f7f7f7}
.container{display:flex;flex-wrap:wrap;gap:14px}
.panel{flex:1 1 300px;min-width:300px;background:#fff;padding:16px;border-radius:12px;box-shadow:0 0 8px rgba(0,0,0,.1);display:flex;flex-direction:column}
h2{margin:0 0 12px;font-size:18px}
#kassBar{background:#1d4ed8;color:#fff;padding:7px 14px;margin:-16px -16px 12px;border-radius:12px 12px 0 0;display:flex;align-items:center;gap:10px;font-size:14px}
#kassBar select{border-radius:5px;padding:3px 7px;font-size:13px;border:none}
#syncStatus{margin-left:auto;font-size:12px;opacity:.85}
.cart-box{flex:1 1 0;min-height:80px;overflow-y:auto;margin-bottom:8px;padding:8px;border-radius:8px;background:#f9fafb;border:2px dashed #bbb}
.empty-cart{color:#999;text-align:center;margin-top:16px;font-style:italic;font-size:14px}
#cartDiscount{font-weight:bold;margin:4px 0;font-size:13px}
.top-left{display:flex;gap:14px;flex-wrap:wrap}
.top-left>div{flex:1 1 180px;min-width:180px;display:flex;flex-direction:column}
.number-pad{display:flex;gap:5px;flex-wrap:nowrap;overflow-x:auto;margin-bottom:10px}
.stats-line{background:#f0f0f0;border-radius:8px;font-size:12px;padding:5px 9px;white-space:nowrap;overflow:hidden}
.pay-pad{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}
.number-button{font-size:17px;padding:11px;border:none;border-radius:8px;cursor:pointer;background:#74b9ff;color:#fff}
.number-button.highlight{box-shadow:0 0 0 3px #0984e3 inset}
.special-btn{background:#a29bfe}
.action-col{display:flex;flex-direction:column;gap:8px;min-width:160px}
.action-col button{width:100%}
.quick-btn{font-size:16px;color:#000}
.quick-btn[data-val="10"]{background:#16a34a;color:#fff}
.quick-btn[data-val="20"]{background:#eab308}
.quick-btn[data-val="50"]{background:#dc5a21;color:#fff}
button{font-size:14px;border:none;border-radius:5px;padding:9px 12px;cursor:pointer}
.small-btn{background:#b2bec3;color:#2d3436;width:100%}
.danger-btn{background:#d63031;color:#fff;width:100%}
.pay-btn{background:#e17055;color:#fff;width:100%;font-size:16px}
.pay-row{display:flex;gap:8px;margin-top:8px}
.pay-row button{flex:1}
#productButtons{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.product-button{width:100%;padding:10px;font-size:14px;text-align:left;border-radius:8px;border:none;cursor:pointer;color:#fff}
.category{grid-column:1/-1;font-weight:bold;margin:14px 0 4px;font-size:14px}
.cart-item{display:grid;grid-template-columns:1fr 100px auto auto auto;align-items:center;gap:8px;font-size:14px;margin-bottom:6px}
.cart-sum{text-align:center}
button.cart-op{padding:0 7px;font-size:14px;background:#dfe6e9;color:#2d3436}
.disabled-cart{filter:grayscale(1);opacity:.4}
.pay-section{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.display-box{font-size:26px;padding:10px;border:2px solid #0984e3;width:220px;text-align:right;background:#fff;border-radius:6px;margin-bottom:8px;box-shadow:0 0 8px rgba(9,132,227,.3)}
.totals-box{width:220px;background:#f1f2f6;border-radius:6px;padding:8px;margin-bottom:8px;font-size:17px;border:2px solid #0984e3;box-shadow:0 0 8px rgba(9,132,227,.3)}
.totals-box div{display:flex;justify-content:space-between}
.change{font-size:17px;font-weight:bold;color:#d63031}
.change.positive{color:#16a34a!important}
.history-item{font-size:12px;border-bottom:1px solid #ccc;padding:2px 0}
#paymentHistory{max-height:100px;overflow-y:auto}
</style>
<script src="https://www.gstatic.com/firebasejs/11.6.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/11.6.1/firebase-database-compat.js"></script>
<script>
const firebaseConfig={apiKey:"AIzaSyB5wSCzf7cbCyi4NjMoDY8XD_FfAwl0LMw",authDomain:"kasse-thp.firebaseapp.com",databaseURL:"https://kasse-thp-default-rtdb.europe-west1.firebasedatabase.app",projectId:"kasse-thp",storageBucket:"kasse-thp.appspot.com",messagingSenderId:"649959661531",appId:"1:649959661531:web:f48ac1a2a41bd7eff851fe"};
firebase.initializeApp(firebaseConfig);
const db=firebase.database();
const products=[],categoryList={},cart={},soldStats={},paymentHistory=[];
let soldRevenue=0;
db.ref('state').on('value',snap=>{const s=snap.val();if(!s)return;products.length=0;products.push(...(s.products||[]));Object.assign(categoryList,s.categoryList||{});Object.assign(cart,s.cart||{});Object.assign(soldStats,s.soldStats||{});soldRevenue=s.soldRevenue||0;paymentHistory.length=0;paymentHistory.push(...(s.paymentHistory||[]));if(typeof renderProducts==='function'){renderProducts();renderCart();updateHistory();}});
function persist(){db.ref('state').set({products,categoryList,cart,soldStats,soldRevenue,paymentHistory});}
window.addEventListener('beforeunload',persist);
window.addEventListener('unload',persist);
</script>
</head>
<body>
<div class="container">
  <div class="panel">
    <div id="kassBar">
      <span>Kassierer:</span>
      <select id="kassSelect">
        <option>Freddy</option><option>Divin</option><option>Chrissi</option>
        <option>Jan</option><option>Leul</option><option>Sohrab</option>
        <option>Aldar</option><option>Lorena</option><option>Anna K.</option>
        <option>Michelle</option><option>Finn</option>
      </select>
      <span id="syncStatus"></span>
    </div>
    <div class="top-left">
      <div>
        <h2>Anzahl</h2>
        <div id="quantityPad" class="number-pad"></div>
        <div id="statView" class="stats-line"></div>
      </div>
    </div>
    <div id="productButtons"></div>
  </div>
  <div class="panel">
    <h2>Warenkorb</h2>
    <div class="cart-box"><div id="cartItems"></div><div id="cartDiscount"></div></div>
    <div class="pay-section">
      <div>
        <div id="payAmountDisplay" class="display-box">0 EUR</div>
        <div class="totals-box">
          <div><span>Gesamt:</span><span id="total">0.00 EUR</span></div>
          <div class="change"><span>Rueckgeld:</span><span id="change">0.00 EUR</span></div>
        </div>
        <div id="payPad" class="pay-pad"></div>
        <div class="pay-row">
          <button class="pay-btn" onclick="checkout()">Zahlung abschliessen</button>
          <button class="danger-btn" onclick="cancelOrder()">Stornieren</button>
        </div>
      </div>
      <div class="action-col">
        <button id="discountBtn" class="small-btn" onclick="toggleDiscount()">Rabatt</button>
        <button class="small-btn" onclick="makeFree()">Gratis</button>
        <button class="quick-btn" data-val="10" onclick="quickPay(10)">10 EUR</button>
        <button class="quick-btn" data-val="20" onclick="quickPay(20)">20 EUR</button>
        <button class="quick-btn" data-val="50" onclick="quickPay(50)">50 EUR</button>
        <button class="quick-btn" onclick="exactPay()">Passend</button>
      </div>
    </div>
    <div style="margin:10px 0 4px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="small-btn" onclick="showFullHistory()">Alle Umsaetze</button>
      <button class="small-btn" onclick="showStatsWindow()">Statistik</button>
    </div>
    <div id="paymentHistory"></div>
  </div>
</div>
<script>
products.push(
  {name:'Bier',price:2.0,category:'Classics',color:'#00b894'},
  {name:'Aeppler 0,33',price:3.0,category:'Classics',color:'#0984e3'},
  {name:'+Pfand',price:0.5,category:'Classics',color:'#b6b904'},
  {name:'Shot',price:1.5,category:'Shots',color:'#0984e3'},
  {name:'Surprise Shot',price:0.5,category:'Shots',color:'#0984e3'},
  {name:'Happy Hour Shot',price:1.0,category:'Shots',color:'#0984e3'},
  {name:'Spezi',price:2.0,category:'alkoholfrei',color:'#00b894'},
  {name:'Mate',price:3.0,category:'alkoholfrei',color:'#00b894'},
  {name:'+Pfand',price:0.5,category:'alkoholfrei',color:'#b6b904'},
  {name:'Limo 0,33',price:1.5,category:'alkoholfrei',color:'#0984e3'},
  {name:'Red Bull',price:3.0,category:'alkoholfrei',color:'#0984e3'},
  {name:'Sekt Mate',price:4.0,category:'Mischen',color:'#00b894'},
  {name:'Vodka Mate',price:4.0,category:'Mischen',color:'#00b894'},
  {name:'+Pfand',price:0.5,category:'Mischen',color:'#b6b904'},
  {name:'Koks Mische',price:5.0,category:'Mischen',color:'#0984e3'},
  {name:'Flasche Pfeffi',price:15.0,category:'Specials',color:'#0984e3'},
  {name:'Golfclub',price:15.0,category:'Specials',color:'#0984e3'},
  {name:'ACAB',price:110.0,category:'Specials',color:'#0984e3'},
  {name:'Bierpong',price:15.0,category:'Specials',color:'#0984e3'},
  {name:'Mischkonsum',price:15.0,category:'Specials',color:'#0984e3'},
  {name:'Schmeisse Runde',price:16.0,category:'Specials',color:'#0984e3'}
);
function rebuildCategories(){for(const k in categoryList)delete categoryList[k];products.forEach(p=>(categoryList[p.category]=categoryList[p.category]||[]).push(p));}
rebuildCategories();
let selectedQuantity=1,payAmount="",discountInput="",freeInvoice=false,mode="pay";
const paymentHistoryEl=document.getElementById('paymentHistory');
const statView=document.getElementById('statView');
const nBtn=(txt,extra='')=>{const b=document.createElement('button');b.textContent=txt;b.className='number-button'+(extra?' '+extra:'');return b;};
function renderQuantityPad(){const pad=document.getElementById('quantityPad');pad.innerHTML='';['1','2','3','4','5','6','7','8','9','0','C'].forEach(l=>{const b=nBtn(l);b.onclick=()=>handleQuantity(l,b);pad.appendChild(b);});}
function handleQuantity(l,btn){if(l==='C'){selectedQuantity=1;document.querySelectorAll('#quantityPad .number-button').forEach(x=>x.classList.remove('highlight'));}else{selectedQuantity=+l;document.querySelectorAll('#quantityPad .number-button').forEach(x=>x.classList.remove('highlight'));btn.classList.add('highlight');}}
function renderProducts(){const wrap=document.getElementById('productButtons');wrap.innerHTML='';for(const cat in categoryList){wrap.insertAdjacentHTML('beforeend',`<div class="category">${cat}</div>`);categoryList[cat].forEach(p=>{const b=document.createElement('button');b.className='product-button';b.style.background=p.color;b.textContent=p.name+' - '+p.price.toFixed(2)+' EUR';b.onclick=()=>{(cart[p.name]=cart[p.name]||{...p,quantity:0}).quantity+=selectedQuantity;selectedQuantity=1;renderCart();document.querySelectorAll('#quantityPad .number-button').forEach(x=>x.classList.remove('highlight'));persist();};wrap.appendChild(b);});}}
function calcTotal(base){let d=0;if(discountInput)d=discountInput.endsWith('%')?base*(parseFloat(discountInput)/100||0):parseFloat(discountInput.replace(',','.'))||0;if(freeInvoice)d=base;return Math.max(0,base-d);}
function renderCart(){const c=document.getElementById('cartItems');c.innerHTML='';let pre=0;for(const k in cart){const it=cart[k],sum=it.quantity*it.price;pre+=sum;const d=document.createElement('div');d.className='cart-item';d.innerHTML='<span>'+it.quantity+'x '+it.name+' a '+it.price.toFixed(2)+' EUR</span><span class="cart-sum">= '+sum.toFixed(2)+' EUR</span>';['+','-','x'].forEach(sym=>{const b=document.createElement('button');b.className='cart-op';b.textContent=sym;if(sym==='+')b.onclick=()=>{it.quantity++;renderCart();persist();};else if(sym==='-')b.onclick=()=>{if(--it.quantity<=0)delete cart[k];renderCart();persist();};else b.onclick=()=>{delete cart[k];renderCart();persist();};d.appendChild(b);});c.appendChild(d);}if(Object.keys(cart).length===0)c.innerHTML='<div class="empty-cart">Warenkorb leer</div>';cartDiscount.textContent=freeInvoice?'Rabatt: 100%':discountInput?'Rabatt: '+(discountInput.endsWith('%')?discountInput:discountInput+' EUR'):'';total.textContent=calcTotal(pre).toFixed(2);c.classList.toggle('disabled-cart',freeInvoice);updateChange();renderStats();}
function renderPayPad(){const pad=document.getElementById('payPad');pad.innerHTML='';['7','8','9','4','5','6','1','2','3','0','%','E','.','C','<'].forEach(l=>{const b=nBtn(l,(l==='E'||l==='%'?'special-btn':''));b.onclick=()=>handlePay(l);pad.appendChild(b);});}
function handlePay(l){if(l==='C'){mode==='discount'?discountInput='':payAmount='';}else if(l==='<'){mode==='discount'?discountInput=discountInput.slice(0,-1):payAmount=payAmount.slice(0,-1);}else if(l==='E'){if(mode==='discount'&&discountInput.endsWith('%'))discountInput=discountInput.slice(0,-1);}else if(l==='%'){if(mode==='discount'&&!discountInput.endsWith('%'))discountInput+='%';}else{mode==='discount'?discountInput+=l:payAmount+=l;}updateDisplays();renderCart();}
function updateDisplays(){payAmountDisplay.textContent=mode==='discount'?'Rabatt: '+(discountInput.endsWith('%')?discountInput:(discountInput||'0')+' EUR'):(payAmount||'0')+' EUR';}
function updateChange(){const diff=parseFloat((payAmount||'0').replace(',','.'))-parseFloat(total.textContent);change.textContent=isNaN(diff)?'0.00 EUR':diff.toFixed(2)+' EUR';diff>0?change.classList.add('positive'):change.classList.remove('positive');}
function toggleDiscount(){if(mode!=='discount'){mode='discount';discountBtn.textContent='Rabatt speichern';}else{mode='pay';discountBtn.textContent='Rabatt';renderCart();updateDisplays();persist();}}
function makeFree(){freeInvoice=!freeInvoice;renderCart();persist();}
const quickPay=v=>{mode='pay';payAmount=String(v);updateDisplays();updateChange();};
function exactPay(){mode='pay';payAmount=parseFloat(total.textContent).toFixed(2);updateDisplays();updateChange();}
function cancelOrder(){if(confirm('Bestellung wirklich stornieren?')){for(const k in cart)delete cart[k];payAmount=discountInput='';freeInvoice=false;mode='pay';renderCart();updateDisplays();persist();}}
function checkout(){
  if(mode==='discount')toggleDiscount();
  const totalNum=parseFloat(total.textContent),recv=parseFloat((payAmount||'0').replace(',','.'))||0;
  if(!freeInvoice&&recv<totalNum){alert('Betrag zu gering!');return;}
  const changeVal=(recv-totalNum).toFixed(2);
  const itemList=Object.values(cart);
  const items=itemList.map(x=>x.quantity+'x '+x.name).join(', ');
  const anzahl=itemList.reduce((s,x)=>s+x.quantity,0);
  const kassierer=document.getElementById('kassSelect').value;
  const ts=new Date().toLocaleString('de-DE');
  const entry=new Date().toLocaleTimeString()+' ['+kassierer+'] - '+totalNum.toFixed(2)+' EUR | '+items;
  paymentHistory.unshift(entry);updateHistory();
  for(const k in cart)soldStats[k]=(soldStats[k]||0)+cart[k].quantity;
  soldRevenue+=totalNum;
  window.parent.postMessage({type:'checkout',zeitstempel:ts,produkte:items,anzahl_gesamt:anzahl,betrag:totalNum,erhalten:recv,rueckgeld:parseFloat(changeVal),rabatt:freeInvoice?'100%':(discountInput||''),kassierer:kassierer},'*');
  document.getElementById('syncStatus').textContent='Gespeichert';
  alert('Zahlung erfolgreich!\\n'+entry);
  for(const k in cart)delete cart[k];
  payAmount=discountInput='';freeInvoice=false;renderCart();updateDisplays();persist();
}
function updateHistory(){paymentHistoryEl.innerHTML=paymentHistory.slice(0,5).map(e=>'<div class="history-item">'+e+'</div>').join('');}
function renderStats(){const pieces=Object.values(soldStats).reduce((s,n)=>s+n,0);statView.textContent='TX: '+paymentHistory.length+'  Stueck: '+pieces+'  '+soldRevenue.toFixed(2)+' EUR';}
function showStatsWindow(){const w=open('','_blank'),pieces=Object.values(soldStats).reduce((s,n)=>s+n,0);w.document.write('<h2>Umsatzstatistik</h2><table border=1 cellpadding=6>');for(const p in soldStats)w.document.write('<tr><td>'+p+'</td><td>'+soldStats[p]+'</td></tr>');w.document.write('<tr style="font-weight:bold"><td>Summe Stueck</td><td>'+pieces+'</td></tr><tr style="font-weight:bold"><td>Gesamtumsatz</td><td>'+soldRevenue.toFixed(2)+' EUR</td></tr></table>');}
function showFullHistory(){const w=open('','_blank');w.document.write('<h2>Alle Umsaetze</h2>');paymentHistory.forEach(e=>w.document.write('<div>'+e+'</div>'));}
renderQuantityPad();renderPayPad();renderProducts();renderCart();
</script>
</body>
</html>"""


def get_gspread_client():
    try:
        secrets = dict(st.secrets)
    except StreamlitSecretNotFoundError:
        secrets = {}
    if "gcp_service_account" in secrets:
        return gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
    for candidate in SERVICE_ACCOUNT_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            if candidate.suffix.lower() == ".json":
                return gspread.service_account(filename=str(candidate))
            credentials = json.loads(candidate.read_text(encoding="utf-8").strip())
            return gspread.service_account_from_dict(credentials)
        except Exception as exc:
            st.warning(f"Anmeldedatei konnte nicht genutzt werden: {candidate} ({exc})")
    raise FileNotFoundError("Keine Google-Service-Account-Datei gefunden.")


@st.cache_resource
def get_worksheet():
    client = get_gspread_client()
    ss = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = ss.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=SHEET_NAME, rows=2000, cols=len(HEADER))
        ws.append_row(HEADER)
        ws.freeze(rows=1)
    return ws


def append_kasse_row(data: dict):
    ws = get_worksheet()
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    tx_id = "KS-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    ws.append_row([
        tx_id,
        data.get("zeitstempel", now),
        data.get("produkte", ""),
        data.get("anzahl_gesamt", 0),
        data.get("betrag", 0),
        data.get("erhalten", 0),
        data.get("rueckgeld", 0),
        data.get("rabatt", ""),
        data.get("kassierer", ""),
    ], value_input_option="USER_ENTERED")
    load_kasse.clear()


@st.cache_data(ttl=30)
def load_kasse():
    ws = get_worksheet()
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return pd.DataFrame(columns=HEADER)
    data = []
    for row in rows[1:]:
        padded = row[:len(HEADER)] + [""] * (len(HEADER) - len(row))
        if not any(str(c).strip() for c in padded):
            continue
        data.append(dict(zip(HEADER, padded)))
    if not data:
        return pd.DataFrame(columns=HEADER)
    df = pd.DataFrame(data)
    df["Betrag_Gesamt"] = pd.to_numeric(df["Betrag_Gesamt"], errors="coerce").fillna(0.0)
    df["Anzahl_Gesamt"] = pd.to_numeric(df["Anzahl_Gesamt"], errors="coerce").fillna(0)
    df["Zeitstempel"] = pd.to_datetime(df["Zeitstempel"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    return df


def format_euro(v):
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


st.set_page_config(page_title="THP - Kasse", page_icon="🍺", layout="wide")
st.title("🍺 Touch-Kasse")

kasse_tab, auswertung_tab = st.tabs(["Kasse", "Auswertung"])

with kasse_tab:
    st.caption("Kassierer waehlen, Produkte antippen, Betrag eingeben, Zahlung abschliessen.")

    with st.form("checkout_form", clear_on_submit=True):
        st.markdown("**Nach der Zahlung ins Sheet eintragen:**")
        fc1, fc2, fc3, fc4 = st.columns([2, 1, 3, 1])
        with fc1:
            f_kassierer = st.selectbox("Kassierer", ["Freddy","Divin","Chrissi","Jan","Leul","Sohrab","Aldar","Lorena","Anna K.","Michelle","Finn"])
        with fc2:
            f_betrag = st.number_input("Betrag (EUR)", min_value=0.0, step=0.5, format="%.2f")
        with fc3:
            f_produkte = st.text_input("Produkte", placeholder="2x Bier, 1x Mate, 1x Shot")
        with fc4:
            f_rabatt = st.text_input("Rabatt", placeholder="10% oder leer")
        f_submit = st.form_submit_button("Ins Sheet speichern", type="primary")

    if f_submit and f_betrag > 0:
        anzahl = 0
        for teil in f_produkte.split(","):
            teil = teil.strip()
            if "x " in teil:
                try:
                    anzahl += int(teil.split("x ")[0].strip())
                except ValueError:
                    pass
        append_kasse_row({
            "kassierer": f_kassierer,
            "betrag": f_betrag,
            "erhalten": f_betrag,
            "rueckgeld": 0,
            "produkte": f_produkte,
            "anzahl_gesamt": anzahl,
            "rabatt": f_rabatt,
        })
        st.success(f"{format_euro(f_betrag)} von {f_kassierer} gespeichert.")
        st.rerun()

    components.html(KASSE_HTML, height=820, scrolling=True)

with auswertung_tab:
    if st.button("Daten neu laden"):
        load_kasse.clear()
        st.rerun()

    df = load_kasse()

    if df.empty:
        st.info("Noch keine Kassendaten vorhanden.")
        st.stop()

    gesamtumsatz = df["Betrag_Gesamt"].sum()
    transaktionen = len(df)
    schnitt = gesamtumsatz / transaktionen if transaktionen > 0 else 0
    stueck_gesamt = df["Anzahl_Gesamt"].sum()

    m = st.columns(4)
    m[0].metric("Gesamtumsatz", format_euro(gesamtumsatz))
    m[1].metric("Transaktionen", str(transaktionen))
    m[2].metric("Durchschnitt", format_euro(schnitt))
    m[3].metric("Artikel verkauft", str(int(stueck_gesamt)))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Umsatz pro Transaktion")
        time_df = df.dropna(subset=["Zeitstempel"]).sort_values("Zeitstempel")
        if not time_df.empty:
            fig = px.bar(time_df, x="Zeitstempel", y="Betrag_Gesamt", color="Kassierer",
                         labels={"Betrag_Gesamt": "Betrag (EUR)", "Zeitstempel": "Zeit"}, height=300)
            fig.update_layout(margin={"l":10,"r":10,"t":10,"b":10})
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Umsatz pro Kassierer")
        kass_df = df.groupby("Kassierer")["Betrag_Gesamt"].sum().reset_index().sort_values("Betrag_Gesamt", ascending=False)
        fig2 = go.Figure(go.Bar(x=kass_df["Kassierer"], y=kass_df["Betrag_Gesamt"],
                                text=[format_euro(v) for v in kass_df["Betrag_Gesamt"]],
                                textposition="outside", marker_color="#1d4ed8"))
        fig2.update_layout(height=300, margin={"l":10,"r":10,"t":10,"b":10}, yaxis_title="EUR")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Meistverkaufte Produkte")
    product_counts: dict = {}
    for _, row in df.iterrows():
        for teil in str(row["Produkte"]).split(","):
            teil = teil.strip()
            if not teil or "x " not in teil:
                continue
            try:
                menge, name = teil.split("x ", 1)
                product_counts[name.strip()] = product_counts.get(name.strip(), 0) + int(menge.strip())
            except ValueError:
                continue

    if product_counts:
        prod_df = pd.DataFrame(sorted(product_counts.items(), key=lambda x: x[1], reverse=True), columns=["Produkt", "Stueck"])
        fig3 = go.Figure(go.Bar(x=prod_df["Produkt"], y=prod_df["Stueck"],
                                text=prod_df["Stueck"], textposition="outside", marker_color="#16a34a"))
        fig3.update_layout(height=340, margin={"l":10,"r":10,"t":10,"b":10}, yaxis_title="Stueck")
        st.plotly_chart(fig3, use_container_width=True)

    with st.expander("Alle Buchungen", expanded=False):
        display = df.copy()
        display["Zeitstempel"] = display["Zeitstempel"].dt.strftime("%d.%m.%Y %H:%M").fillna("-")
        display["Betrag_Gesamt"] = display["Betrag_Gesamt"].map(format_euro)
        st.dataframe(display[["Zeitstempel","Kassierer","Produkte","Anzahl_Gesamt","Betrag_Gesamt","Rabatt"]],
                     use_container_width=True, hide_index=True)
