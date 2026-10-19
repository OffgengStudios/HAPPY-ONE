(function(root) {
  'use strict';
  const optional = value => String(value || '').trim() || null;
  function buildPayload(company, vacancies, documents, submissionId) {
    const data = { submission_id: submissionId };
    ['company_name','sector','industry','region','district','city','address','website',
      'contact_name','contact_role','contact_phone','contact_email','partnership_start_date'].forEach(key => { data[key] = optional(company[key]); });
    data.partnership_type = company.partnership_type || 'RECRUITMENT';
    data.consent_agreement = company.consent_agreement === true || company.consent_agreement === 'on';
    data.consent_contact = company.consent_contact === true || company.consent_contact === 'on';
    data.company_fax = company.company_fax || '';
    data.vacancies = vacancies.map(item => ({
      job_title: item.job_title, location: item.location, employment_type: item.employment_type,
      openings: Number(item.openings), description: optional(item.description),
      salary_min: optional(item.salary_min), salary_max: optional(item.salary_max),
      salary_frequency: optional(item.salary_frequency), work_days: optional(item.work_days),
      work_hours: optional(item.work_hours), deadline: optional(item.deadline),
      accommodation: item.accommodation === '' ? null : item.accommodation === 'yes',
      benefits: String(item.benefits || '').split('\n').map(v => v.trim()).filter(Boolean),
      requirements: ['education','experience','skills','licenses','certifications','language','eligibility'].flatMap(kind =>
        String(item[kind] || '').split('\n').map(v => v.trim()).filter(Boolean).map((value, index) => ({
          criterion_type: kind.toUpperCase(), criterion_key: kind.toUpperCase() + '_' + index,
          operator: 'EQ', value_json: value, is_required: true, weight: 1, display_order: index + 1
        })))
    }));
    data.documents = documents;
    return data;
  }
  const api = { buildPayload };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.EmployerIntake = api;
}(typeof window === 'undefined' ? globalThis : window));
