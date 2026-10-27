const fs=require("fs"),path=require("path"),{JSDOM,VirtualConsole}=require("jsdom");
const WEB="/home/user/sigma-brvm/sigma-app/web";
const DATA=fs.readFileSync(path.join(WEB,"data/data.json"),"utf8");
const erreurs=[];const vc=new VirtualConsole();
vc.on("jsdomError",e=>erreurs.push(String(e.message||e)));vc.on("error",m=>erreurs.push(String(m)));
const dom=new JSDOM(fs.readFileSync(path.join(WEB,"index.html"),"utf8"),{runScripts:"outside-only",pretendToBeVisual:true,url:"http://localhost/",virtualConsole:vc});
const w=dom.window;
w.fetch=()=>Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(JSON.parse(DATA)),clone(){return this;}});
w.matchMedia=w.matchMedia||(()=>({matches:false,addListener(){},removeListener(){}}));
w.requestAnimationFrame=cb=>setTimeout(()=>cb(Date.now()),0);w.scrollTo=()=>{};
if(!w.HTMLDialogElement)w.HTMLDialogElement=w.HTMLElement;
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(){this.open=false;};
try{w.eval(fs.readFileSync(path.join(WEB,"app.js"),"utf8"));}catch(e){erreurs.push("EVAL "+e.message);}
const att=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  await att(900);
  const out={};
  for(const vue of ["accueil","entreprises","actualites","decision","portefeuille","parametres","marche","alertes"]){
    erreurs.length=0;
    const bouton=w.document.querySelector(`.nav-item[data-view="${vue}"]`);
    if(bouton){bouton.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));}
    else{const lien=w.document.querySelector(`[data-view-link="${vue}"]`);lien?lien.dispatchEvent(new w.MouseEvent("click",{bubbles:true})):erreurs.push("pas de lien "+vue);}
    await att(350);
    const actif=w.document.querySelector(".view.is-active");
    const rempli=actif?(actif.textContent||"").trim().length:0;
    out[vue]={erreurs:[...erreurs], vue_active:actif?actif.id:null, caracteres:rempli};
  }
  // fiche société
  erreurs.length=0;
  const f=w.document.querySelector('[data-open-company]');
  if(f){f.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));}else erreurs.push("pas de lien fiche");
  await att(350);
  out.fiche_snts={erreurs:[...erreurs], vue_active:w.document.querySelector(".view.is-active")?.id||null};
  console.log(JSON.stringify(out,null,1));
  const ko=Object.entries(out).filter(([k,v])=>v.erreurs.length>0 || (k!=="fiche_snts" && (!v.vue_active || v.caracteres<50)));
  process.exit(ko.length?1:0);
})();
