'use strict';
// Existing form controls retained without legacy network or credential code.
function setSubmitting(buttonId, busy) {
  const btn = $(buttonId);
  if (!btn) return;
  btn.disabled = busy;
  const label  = btn.dataset.label || btn.textContent;
  if (busy) { btn.dataset.label = label; btn.textContent = 'Please wait…'; }
  else      { btn.textContent = btn.dataset.label || label; }
}

// ─── CASCADING DROPDOWNS ─────────────────────────────────────────────────────

function onRegionChange(selectId) {
  const region = $(selectId || 'pi-region')?.value || '';
  populateDistricts(region, 'pi-district');
  setValue('pi-district', '');
}

function onSectorChange(selectId) {
  const sector = $(selectId || 'pi-sector')?.value || '';
  populateIndustries(sector, 'pi-industry');
  setValue('pi-industry', '');
  setValue('pi-jobRole', '');
}

function onIndustryChange(selectId) {
  const sector   = $('pi-sector')?.value   || '';
  const industry = $(selectId || 'pi-industry')?.value || '';
  populateJobRoles(sector, industry, 'pi-jobRole');
  setValue('pi-jobRole', '');
}

// Adapts the Sector & Job section to employment status: employed/trainee answer
// about CURRENT work (+ occupation field); unemployed/student answer about the
// work they WANT (occupation hidden). Falls back to neutral labels when unset.
function onEmploymentStatusChange() {
  const status = ($('pi-employmentStatus')?.value || '').trim();

  const MODES = {
    'Employed full-time': 'current',
    'Employed part-time': 'current',
    'Self-employed':      'current',
    'Apprentice / Trainee': 'trade',
    'Unemployed':         'interest',
    'Student':            'interest',
  };
  const mode = MODES[status] || 'neutral';

  const CFG = {
    current:  { title: 'Your Current Work',     hint: 'Tell us about the work you currently do.',
                sector: 'Sector you work in', industry: 'Industry', role: 'Your role / job',
                occ: true, occLabel: 'Job title / occupation' },
    trade:    { title: 'Your Trade & Work',     hint: 'Tell us about your trade or the work you are training in.',
                sector: 'Sector of your trade', industry: 'Industry', role: 'Trade / role',
                occ: true, occLabel: 'Current trade / occupation' },
    interest: { title: 'Work Interest',         hint: (status === 'Student' ? 'Tell us the kind of work you would like after your studies.' : 'Tell us the kind of work you are looking for.'),
                sector: 'Sector you want to work in', industry: 'Industry of interest', role: 'Role you are seeking',
                occ: false, occLabel: '' },
    neutral:  { title: 'Sector & Job Interest', hint: '',
                sector: 'Sector', industry: 'Industry', role: 'Job Role', occ: false, occLabel: '' },
  };
  const c = CFG[mode];

  setText('pi-sector-section-title', c.title);
  setText('pi-sector-label',   c.sector);
  setText('pi-industry-label', c.industry);
  setText('pi-jobRole-label',  c.role);

  const hint = $('pi-sector-hint');
  if (hint) { hint.textContent = c.hint; toggle('pi-sector-hint', !!c.hint); }

  toggle('pi-occupation-group', c.occ);
  if (c.occ && c.occLabel) setText('pi-currentOccupation-label', c.occLabel);

  // Income + place-of-work details only make sense for people currently working.
  toggle('pi-current-work-group', mode === 'current' || mode === 'trade');
}

// Nationality is asked only when the participant is a refugee.
function onRefugeeChange() {
  const isRefugee = ($('pi-refugeeStatus')?.value || '') === 'Yes';
  toggle('pi-nationality-group', isRefugee);
  if (!isRefugee) setValue('pi-nationality', '');
}

// Capacity-building: training sector → industry (same taxonomy as placements).
function onTrainingSectorChange() {
  populateIndustries($('cb-trainingSector')?.value || '', 'cb-trainingIndustry');
  setValue('cb-trainingIndustry', '');
}
