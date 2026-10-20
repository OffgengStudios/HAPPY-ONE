'use strict';
const form = document.querySelector('#employer-form');
const draftKey = 'happy_employer_draft_v1';
let submissionId = crypto.randomUUID();
let configuration = null;
let pending = null;
const attachments = [];
const endpoint = () => String(window.HAPPY_API_BASE_URL || '').replace(/\/$/,'');
const values = element => Object.fromEntries(Array.from(element.querySelectorAll('input,select,textarea')).filter(el => el.name && el.type !== 'file').map(el => [el.name, el.type === 'checkbox' ? el.checked : el.value]));
const vacancies = () => Array.from(document.querySelectorAll('.vacancy')).map(values);
function status(message, error=false) { const el=document.querySelector('#status'); el.hidden=!message; el.textContent=message; el.className='status'+(error?' error':''); }
function addVacancy(data={}) {
  if(document.querySelectorAll('.vacancy').length>=20) return;
  const card=document.querySelector('#vacancy-template').content.cloneNode(true);
  card.querySelectorAll('[name]').forEach(el => { if(data[el.name] !== undefined) el.value=data[el.name]; });
  card.querySelector('button').addEventListener('click',event=>{ if(document.querySelectorAll('.vacancy').length>1) { event.target.closest('.vacancy').remove(); save(); } });
  document.querySelector('#vacancies').append(card);
}
function save(edited=false) {
  if(edited || pending) { pending=null; submissionId=crypto.randomUUID(); }
  const company=values(document.querySelector('#company'));
  try { sessionStorage.setItem(draftKey,JSON.stringify({updatedAt:Date.now(),submissionId,company,vacancies:vacancies()})); document.querySelector('#draft-status').textContent='Unfinished form saved in this browser tab.'; }
  catch(_) { document.querySelector('#draft-status').textContent='Keep this page open; this browser cannot save the draft.'; }
}
function build() { return EmployerIntake.buildPayload(values(document.querySelector('#company')),vacancies(),attachments.map(item=>({kind:item.kind,vacancy_index:item.vacancy_index})),submissionId); }
function review(event) {
  event.preventDefault();
  if(!form.reportValidity()) return;
  if(!configuration?.accepting_submissions) {status('The employer intake service is not accepting submissions yet.',true);return;}
  const payload=build();
  const summary=[payload.company_name,payload.contact_name,payload.contact_email,...payload.vacancies.map((vacancy,index)=>(index+1)+'. '+vacancy.job_title+' - '+vacancy.location+' - '+vacancy.openings+' opening(s)'),...attachments.map(item=>item.kind+': '+item.file.name)];
  document.querySelector('#summary').textContent=summary.join('\n');
  document.querySelector('#review').hidden=false;
  document.querySelector('#review').scrollIntoView({behavior:'smooth'});
}
async function submit() {
  if(!form.reportValidity()) return;
  const button=document.querySelector('#submit');button.disabled=true;
  try {
    if(!pending) pending=build();
    const data=new FormData();data.set('payload',JSON.stringify(pending));
    attachments.forEach(item=>data.append('files',item.file));
    status('Sending your application...');
    const response=await fetch(endpoint()+'/api/v1/employer-intake',{method:'POST',body:data,credentials:'omit'});
    const result=await response.json();
    if(!response.ok) throw new Error(result.error?.message||'Your application could not be accepted.');
    sessionStorage.removeItem(draftKey);
    document.querySelector('#draft-status').textContent='Submitted. Contact the HAPPY team for later changes.';
    document.querySelector('#discard').hidden=true;
    form.hidden=true;document.querySelector('#review').hidden=true;
    const success=document.querySelector('#success');success.hidden=false;
    document.querySelector('#receipt').textContent=result.receipt_id;
    status('');success.scrollIntoView();
  } catch(error) {status((navigator.onLine?error.message:'You are offline. Your draft remains in this tab.')+' You can safely retry the same submission.',true);}
  finally {button.disabled=false;}
}
document.addEventListener('DOMContentLoaded',async()=>{
  let restored=null;
  try {restored=JSON.parse(sessionStorage.getItem(draftKey)||'null');if(restored && Date.now()-restored.updatedAt>86400000){sessionStorage.removeItem(draftKey);restored=null;}}catch(_){}
  if(restored){submissionId=restored.submissionId;document.querySelectorAll('#company [name]').forEach(el=>{if(restored.company[el.name]!==undefined)el.type==='checkbox'?el.checked=restored.company[el.name]:el.value=restored.company[el.name];});restored.vacancies.forEach(addVacancy);}
  else addVacancy();
  form.addEventListener('input',()=>{document.querySelector('#review').hidden=true;save(true);});
  form.addEventListener('submit',review);
  document.querySelector('#add-vacancy').addEventListener('click',()=>{addVacancy();save();});
  document.querySelector('#submit').addEventListener('click',submit);
  document.querySelector('#discard').addEventListener('click',()=>{sessionStorage.removeItem(draftKey);location.reload();});
  document.querySelector('#attach').addEventListener('click',()=>{
    const selected=document.querySelector('#document-file').files[0];
    const kind=document.querySelector('#document-kind').value;
    const index=Number(document.querySelector('#document-vacancy').value)-1;
    if(!selected||!/\.(pdf|docx)$/i.test(selected.name)||selected.size>(configuration?.file_max_bytes||10485760)){status('Choose a PDF or DOCX within the upload limit.',true);return;}
    if(attachments.length>=5){status('Attach at most five documents.',true);return;}
    if(kind==='JD' && (index<0 || index>=vacancies().length)){status('Choose a submitted vacancy number for this job description.',true);return;}
    attachments.push({file:selected,kind,vacancy_index:kind==='JD'?index:null});
    const entry=document.createElement('li');entry.textContent=kind+': '+selected.name;
    const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='Remove';
    const attachment=attachments[attachments.length-1];remove.addEventListener('click',()=>{attachments.splice(attachments.indexOf(attachment),1);entry.remove();save();});entry.append(remove);document.querySelector('#attachments').append(entry);save();
  });
  try{const response=await fetch(endpoint()+'/api/v1/employer-intake/config',{credentials:'omit'});if(!response.ok)throw new Error('The intake service is unavailable.');configuration=await response.json();document.querySelector('#notice').textContent=configuration.notice||'Applications will open once the programme notice is configured.';document.querySelector('#review-button').disabled=!configuration.accepting_submissions;}
  catch(error){status(error.message,true);}
});
