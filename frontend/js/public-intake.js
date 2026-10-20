'use strict';

// No participant authentication, staff sessions, record lookup or internal CRUD.
const DRAFT_KEY = 'happy_hamis_local_draft_v1';
const MAX_DRAFT_AGE = 24 * 60 * 60 * 1000;
let intakeConfig = null;
let chosenCV = null;
let submissionId = crypto.randomUUID();
let storedNoticeVersion = '';
let pendingSubmission = null;

function apiOrigin() { return String(window.HAPPY_API_BASE_URL || '').replace(/\/$/, ''); }
function collectFields(prefix) {
  const values = {};
  document.querySelectorAll('[id^="' + prefix + '-"]').forEach(el => {
    if (!el.matches('input,select,textarea') || el.disabled || el.type === 'file') return;
    values[el.id.slice(prefix.length + 1)] = el.type === 'checkbox' ? (el.checked ? el.value : '') : el.value;
  });
  return values;
}
function saveLocalDraft(event) {
  const edited = event && ['input', 'change'].includes(event.type);
  if (edited || pendingSubmission && event === true) { submissionId = crypto.randomUUID(); pendingSubmission = null; }
  const draft = { updatedAt: Date.now(), submissionId, pi: collectFields('pi'), cb: collectFields('cb'), noticeVersion: storedNoticeVersion };
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    if ($('persist-draft')?.checked) localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    else localStorage.removeItem(DRAFT_KEY);
    setText('draft-status', navigator.onLine ? 'Draft saved on this device. Nothing has been submitted.' : 'Offline. Draft saved on this device.');
  } catch (_) { setText('draft-status', 'This browser could not save your draft. Keep this page open.'); }
}
function restoreLocalDraft() {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY) || localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    const draft = JSON.parse(raw);
    if (!draft.updatedAt || Date.now() - draft.updatedAt > MAX_DRAFT_AGE) { clearDraft(); return; }
    submissionId = draft.submissionId || submissionId;
    storedNoticeVersion = draft.noticeVersion || '';
    prefillParticipantInfoScreen(draft.pi || {});
    Object.entries(draft.cb || {}).forEach(([key, value]) => setValue('cb-' + key, value));
    $('persist-draft').checked = Boolean(localStorage.getItem(DRAFT_KEY));
    setText('draft-status', 'An unfinished draft was restored. Reselect your CV before submitting.');
  } catch (_) { clearDraft(); }
}
function clearDraft() {
  sessionStorage.removeItem(DRAFT_KEY); localStorage.removeItem(DRAFT_KEY);
}
function showReview() {
  const values = collectFields('pi');
  const missing = HamisIntake.validate(values);
  if (missing.length) { showScreen('screen-participant-info'); showStatus('pi-status', 'Please check: ' + missing.join(', '), 'error'); return; }
  setText('review-details', [values.firstName, values.surname].join(' ') + '\n' + values.telephone + '\n' + values.community + '\nCV: ' + (chosenCV ? chosenCV.name : 'Not attached'));
  showScreen('screen-review');
}
async function submitIntake() {
  const button = $('intake-submit');
  button.disabled = true;
  try {
    if (!intakeConfig?.accepting_submissions || storedNoticeVersion !== intakeConfig.privacy_notice_version) throw new Error('Review the current privacy notice before submitting.');
    if (!pendingSubmission) pendingSubmission = HamisIntake.buildPayload(collectFields('pi'), collectFields('cb'), storedNoticeVersion, submissionId);
    const form = new FormData();
    form.set('payload', JSON.stringify(pendingSubmission));
    if (chosenCV) form.set('cv', chosenCV);
    showStatus('review-status', 'Submitting your registration...', 'info');
    const response = await fetch(apiOrigin() + '/api/v1/participant-intake', { method: 'POST', body: form, credentials: 'omit' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message || 'The submission could not be accepted.');
    clearDraft();
    setText('complete-name', 'Thank you for submitting your information.');
    setText('complete-participant-id', result.receipt_id);
    showScreen('screen-complete');
    hide('draft-controls');
    setText('draft-status', 'Submitted. Contact the HAPPY team for later changes.');
  } catch (error) {
    showStatus('review-status', (navigator.onLine ? error.message : 'You are offline. Your draft is saved; reconnect and retry.') + ' You can safely retry the same submission.', 'error');
  } finally { button.disabled = false; }
}
document.addEventListener('DOMContentLoaded', async () => {
  // Discard obsolete legacy credential storage; it is never read or sent.
  ['hk_candidate_token', 'hk_staff_session', 'hk_participant'].forEach(key => sessionStorage.removeItem(key));
  ['pi-ghanaCardId', 'pi-voterId', 'pi-idType'].forEach(id => { if ($(id)) { $(id).disabled = true; $(id).closest('.fld').hidden = true; } });
  populateRegions('pi-region'); populateRegions('pi-workRegion'); populateRegions('cb-trainingRegion'); populateSectors('pi-sector');
  restoreLocalDraft();
  onEmploymentStatusChange(); onRefugeeChange();
  showScreen('screen-consent');
  document.querySelectorAll('#pi-form input,#pi-form select,#pi-form textarea,#cb-form input,#cb-form select,#cb-form textarea').forEach(el => el.addEventListener('change', saveLocalDraft));
  document.querySelectorAll('#pi-form input,#pi-form textarea').forEach(el => el.addEventListener('input', saveLocalDraft));
  $('persist-draft').addEventListener('change', saveLocalDraft);
  $('discard-draft').addEventListener('click', () => { clearDraft(); location.reload(); });
  $('pi-region').addEventListener('change', () => populateDistricts($('pi-region').value, 'pi-district'));
  $('pi-workRegion').addEventListener('change', () => populateDistricts($('pi-workRegion').value, 'pi-workDistrict'));
  $('cb-trainingRegion').addEventListener('change', () => populateDistricts($('cb-trainingRegion').value, 'cb-trainingDistrict'));
  $('pi-sector').addEventListener('change', () => onSectorChange('pi-sector'));
  $('pi-industry').addEventListener('change', () => onIndustryChange('pi-industry'));
  $('consent-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!intakeConfig?.accepting_submissions || !$('consent-accepted').checked) return;
    storedNoticeVersion = intakeConfig.privacy_notice_version;
    saveLocalDraft(); showScreen('screen-participant-info');
  });
  $('pi-form').addEventListener('submit', event => {
    event.preventDefault(); const missing = HamisIntake.validate(collectFields('pi'));
    if (missing.length) { showStatus('pi-status', 'Please check: ' + missing.join(', '), 'error'); return; }
    saveLocalDraft(); showScreen('screen-capacity-building');
  });
  $('cb-form').addEventListener('submit', event => { event.preventDefault(); saveLocalDraft(); showScreen('screen-cv-upload'); });
  $('cv-file-input').addEventListener('change', event => {
    const file = event.target.files[0];
    if (!file) return;
    if (!/\.(pdf|docx)$/i.test(file.name) || file.size > (intakeConfig?.file_max_bytes || 10485760)) {
      showStatus('cv-status', 'Choose a PDF or DOCX within the upload limit.', 'error'); event.target.value = ''; chosenCV = null; return;
    }
    chosenCV = file; saveLocalDraft({type:'change'}); setText('cv-file-name', file.name); show('cv-file-selected');
    showStatus('cv-status', 'Attached for final submission.', 'info');
  });
  $('cv-skip-btn').addEventListener('click', () => { chosenCV = null; showReview(); });
  $('cv-review-btn').addEventListener('click', showReview);
  $('intake-submit').addEventListener('click', submitIntake);
  $('review-edit').addEventListener('click', () => showScreen('screen-participant-info'));
  window.addEventListener('offline', () => setText('draft-status', 'Offline. Your draft remains on this device.'));
  try {
    const response = await fetch(apiOrigin() + '/api/v1/participant-intake/config', { credentials: 'omit' });
    if (!response.ok) throw new Error('The registration service is unavailable.');
    intakeConfig = await response.json();
    setText('privacy-notice', intakeConfig.privacy_notice || 'Registration will open when the programme privacy notice is configured.');
    $('consent-submit').disabled = !intakeConfig.accepting_submissions;
  } catch (error) { showStatus('consent-status', error.message + ' Your draft remains on this device.', 'error'); }
});
