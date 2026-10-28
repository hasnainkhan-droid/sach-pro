    'use strict';
    const $ = id => document.getElementById(id);
    const samples = {
      otp: 'Salam sir, main Easypaisa head office se bol raha hoon. Apka account block hone wala hai. Abhi jo OTP aaya hai wo mujhe bata dain.',
      bisp: 'مبارک ہو! BISP 8171 کے 25,000 روپے منظور ہو گئے ہیں۔ ابھی http://bisp-gov-pk-claim.xyz کھولیں اور اپنا CNIC اور PIN درج کریں۔',
      job: 'Earn Rs 8,000 daily from home by liking videos. Pay Rs 1,500 registration fee to unlock VIP tasks. Limited spots!',
      parcel: 'Pakistan Post Customs: your parcel is held. Pay Rs 4,200 immediately at https://bit.ly/pk-custom-pay to avoid FIR.',
      safe: 'Your debit card ending 4821 was used for PKR 1,250. If this was not you, contact your bank using the official number on the back of your card.'
    };
    let image = null, result = null, language = 'en', history = [], aiAvailable = false;
    let checkBusy = false, checkVersion = 0, controller = null, imageReadVersion = 0;
    const labels = {scam:['High fraud risk','high'], suspicious:['Potentially suspicious','medium'], safe:['No obvious warning signs','low']};
    function error(message){$('formError').textContent=message;$('formError').style.display=message?'block':'none';}
    function invalidateCheck(){
      checkVersion++;
      if(controller){controller.abort();controller=null;}
      checkBusy=false;
      $('analyzeBtn').disabled=false;
      $('analyzeText').textContent='Analyze message safety';
      result=null;
      $('assessment').setAttribute('aria-hidden','true');
      $('resultEmpty').style.display='flex';
    }
    function inputUpdated(){ invalidateCheck(); $('charCount').textContent=`${$('message').value.length} / 5000`; error(''); }
    $('message').addEventListener('input',inputUpdated);
    $('clearBtn').addEventListener('click',()=>{$('message').value='';clearImage();inputUpdated();$('message').focus();});
    $('pasteBtn').addEventListener('click',async()=>{try{const pasted=await navigator.clipboard.readText();$('message').value=pasted.slice(0,5000);inputUpdated();}catch{error('Browser clipboard permission unavailable. Paste with Ctrl + V.');}$('message').focus();});
    document.querySelectorAll('[data-sample]').forEach(el=>el.addEventListener('click',()=>{$('message').value=samples[el.dataset.sample];inputUpdated();$('message').focus();}));
    try{document.documentElement.dataset.theme=localStorage.getItem('sach-theme')==='dark'?'dark':'light';}catch{}
    $('themeBtn').addEventListener('click',()=>{const dark=document.documentElement.dataset.theme==='dark';document.documentElement.dataset.theme=dark?'light':'dark';try{localStorage.setItem('sach-theme',dark?'light':'dark');}catch{}});
    async function config(){try{const response=await fetch('/api/config');const data=await response.json();aiAvailable=!!data.ai_available;}catch{aiAvailable=false;}$('aiOpt').disabled=!aiAvailable;$('aiAvailability').textContent=aiAvailable?'· Available':'· Not configured';}
    config();
    $('aiOpt').addEventListener('change',invalidateCheck);
    function clearImage(){imageReadVersion++;invalidateCheck();image=null;$('preview').src='';$('preview').style.display='none';$('uploadIcon').style.display='grid';$('uploadLabel').textContent='PNG, JPEG or WebP · Maximum 4 MB';$('removeImage').style.display='none';$('imageFile').value='';}
    $('browseBtn').addEventListener('click',()=>$('imageFile').click());
    $('removeImage').addEventListener('click',clearImage);
    $('imageFile').addEventListener('change',e=>{if(e.target.files[0])attachImage(e.target.files[0]);});
    function attachImage(file){
      if(!['image/png','image/jpeg','image/webp'].includes(file.type)){error('Only PNG, JPEG and WebP files are supported.');return;}
      if(file.size>4*1024*1024){error('Screenshot must be smaller than 4 MB.');return;}
      const version=++imageReadVersion;const reader=new FileReader();reader.onload=()=>{if(version!==imageReadVersion)return;invalidateCheck();const dataUrl=String(reader.result);image={base64:dataUrl.split(',')[1],mimeType:file.type,name:file.name};$('preview').src=dataUrl;$('preview').style.display='block';$('uploadIcon').style.display='none';$('uploadLabel').textContent=file.name;$('removeImage').style.display='inline-block';error('');};reader.onerror=()=>error('Could not read the selected screenshot.');reader.readAsDataURL(file);
    }
    const drop=$('dropzone');['dragenter','dragover'].forEach(event=>drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('drag');}));['dragleave','drop'].forEach(event=>drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('drag');}));drop.addEventListener('drop',e=>{if(e.dataTransfer.files[0])attachImage(e.dataTransfer.files[0]);});
    function listInto(target,items,fallback,step){const el=$(target);el.replaceChildren();const localized=items&&items.length?items:[fallback];localized.forEach((value,i)=>{const li=document.createElement('li'),symbol=document.createElement('span'),text=document.createElement('span');symbol.className='point-icon'+(step?' step':'');symbol.textContent=step?String(i+1):'!';text.textContent=value;li.append(symbol,text);el.append(li);});el.classList.toggle('urdu',language==='ur');}
    function updateLanguage(){ $('langEn').setAttribute('aria-pressed',String(language==='en'));$('langUr').setAttribute('aria-pressed',String(language==='ur'));if(result)renderResult(result); }
    $('langEn').addEventListener('click',()=>{language='en';updateLanguage();});$('langUr').addEventListener('click',()=>{language='ur';updateLanguage();});
    function renderResult(data){
      result=data;$('resultEmpty').style.display='none';$('assessment').setAttribute('aria-hidden','false');
      const [heading,level]=labels[data.verdict]||labels.suspicious;
      $('verdictTitle').textContent=heading;$('verdictTitle').className=level;$('scamType').textContent=data.scam_type||'Message review';
      const score=Math.max(0,Math.min(100,Number(data.risk_score)||0));$('riskScore').textContent=score;$('scoreCircle').style.strokeDashoffset=String(251.32*(100-score)/100);$('scoreCircle').style.stroke=level==='high'?'var(--red)':level==='medium'?'var(--orange)':'var(--brand)';
      $('analysisMode').textContent=data.analysis_mode||'Risk assessment';const exp=$('explanation');exp.textContent=(language==='ur'?data.explanation_ur:data.explanation_en)||'No explanation available.';exp.classList.toggle('urdu',language==='ur');
      const flags=language==='ur'?(data.red_flags_ur||data.red_flags):(data.red_flags||[]);const steps=language==='ur'?(data.what_to_do_ur||data.what_to_do):(data.what_to_do||[]);
      $('flagCount').textContent=`${flags.length} signal${flags.length===1?'':'s'}`;listInto('flags',flags,language==='ur'?'کوئی واضح خطرے کی علامت سامنے نہیں آئی۔':'No specific warning patterns were found.',false);listInto('steps',steps,'Check through the official organization before acting.',true);
      const items=Array.isArray(data.indicators)?data.indicators:[];$('indicatorSection').hidden=!items.length;$('indicators').replaceChildren();items.forEach(item=>{const box=document.createElement('div'),top=document.createElement('div'),tag=document.createElement('span'),status=document.createElement('span'),value=document.createElement('code'),desc=document.createElement('p');box.className='indicator';top.className='indicator-type';tag.textContent=(item.type||'contact');status.textContent=item.level==='high'?'Review carefully':'Unverified';if(item.level==='high')status.className='danger';top.append(tag,status);value.textContent=item.value||'';desc.textContent=item.note||'';box.append(top,value,desc);$('indicators').append(box);});
    }
    function report(){if(!result)return'';const explanation=language==='ur'?result.explanation_ur:result.explanation_en;const flags=language==='ur'?(result.red_flags_ur||result.red_flags):(result.red_flags||[]);const steps=language==='ur'?(result.what_to_do_ur||result.what_to_do):(result.what_to_do||[]);return ['SACH — MESSAGE SAFETY REPORT',`Verdict: ${labels[result.verdict]?.[0]||result.verdict}`,`Risk index: ${result.risk_score}/100 (pattern index; not a fraud probability)`,`Assessment: ${result.analysis_mode}`,`Category: ${result.scam_type}`,'','Summary:',explanation,'','Warning signs:',...(flags.length?flags:['No specific warning patterns were found.']).map(x=>`• ${x}`),'','Recommended actions:',...steps.map((x,i)=>`${i+1}. ${x}`),'','Important: No sender identity or website destination has been verified. Never share your OTP, PIN, or CVV.'].join('\n');}
    async function analyze(){if(checkBusy)return;const message=$('message').value.trim();if(!message&&!image){error('Paste a message or attach a screenshot first.');$('message').focus();return;}if(image&&!message&&!$('aiOpt').checked){error('Screenshot-only checks require AI processing with your consent. Please enable AI (if available) or paste the text.');return;}if(image&&!message&&!aiAvailable){error('Screenshot analysis is unavailable. Please paste the text from the image.');return;}
      const btn=$('analyzeBtn');checkBusy=true;const version=++checkVersion;controller=new AbortController();btn.disabled=true;$('analyzeText').textContent='Checking signals…';error('');
      try{const payload={message,allow_ai_processing:!!$('aiOpt').checked};if(image){payload.image_base64=image.base64;payload.image_mime=image.mimeType;}const res=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});const data=await res.json();if(version!==checkVersion)return;if(!res.ok)throw new Error(data.error||'Unable to assess this message.');renderResult(data);if(message){history=[{message,data},...history.filter(h=>h.message!==message)].slice(0,5);renderHistory();}if(window.matchMedia('(max-width: 1020px)').matches){$('assessment').scrollIntoView({behavior:'smooth',block:'start'});}}
      catch(ex){if(version===checkVersion&&ex.name!=='AbortError')error(ex.message||'The request failed. Try again.');}finally{if(version===checkVersion){checkBusy=false;controller=null;btn.disabled=false;$('analyzeText').textContent='Analyze message safety';}}}
    $('analyzeBtn').addEventListener('click',analyze);$('message').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();analyze();}});
    function renderHistory(){$('historySection').style.display=history.length?'flex':'none';$('historyPills').replaceChildren();history.forEach((item)=>{const b=document.createElement('button');b.type='button';b.className='history-pill '+(labels[item.data.verdict]?.[1]||'medium');b.textContent=item.message.slice(0,65)+(item.message.length>65?'…':'');b.addEventListener('click',()=>{$('message').value=item.message;inputUpdated();renderResult(item.data);});$('historyPills').append(b);});}
    $('clearHistory').addEventListener('click',()=>{history=[];renderHistory();});
    $('copyBtn').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(report());const btn=$('copyBtn');btn.textContent='✓ Copied';setTimeout(()=>btn.textContent='Copy summary',1400);}catch{error('Clipboard unavailable. Try Save report instead.');}});
    $('downloadBtn').addEventListener('click',()=>{const blob=new Blob([report()],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='sach-safety-report.txt';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
    $('shareBtn').addEventListener('click',()=>{if(!result)return;const summary=`⚠️ SACH safety warning: ${labels[result.verdict]?.[0]||'Review needed'} (${result.risk_score}/100 risk index). ${language==='ur'?result.explanation_ur:result.explanation_en}\nNever share OTP, PIN or CVV. Verify using the official app. Scores are not guarantees.`;window.open('https://wa.me/?text='+encodeURIComponent(summary),'_blank','noopener,noreferrer');});
    $('printBtn').addEventListener('click',()=>window.print());
