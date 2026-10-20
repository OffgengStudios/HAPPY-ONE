(function (root) {
  'use strict';
  function optional(value) { return String(value || '').trim() || null; }
  function buildPayload(values, training, noticeVersion, submissionId) {
    const supplemental = {};
    ['preferredName', 'participantTypeSupport', 'secondaryPhone', 'referralPhone',
      'referralRelationship', 'guarantorName', 'homeAddress', 'baselineEmploymentType',
      'activeStudent', 'hostCommunity', 'workLocationStatus', 'nationalityOrigin'].forEach(key => {
      if (values[key]) supplemental[key] = values[key];
    });
    const income = optional(values.monthlyIncome);
    return {
      submission_id: submissionId,
      basic: { first_name: values.firstName, surname: values.surname, other_names: optional(values.otherNames) },
      contact: {
        phone_raw: values.telephone, email: optional(values.email), community: values.community,
        region_code: optional(values.region), district_code: optional(values.district),
        location_status: optional(values.locationStatus), directions: optional(values.homeAddress)
      },
      demographics: { date_of_birth: optional(values.dob), sex: optional(values.sex), nationality: optional(values.nationality) },
      education: values.educationLevel ? [{ education_level: values.educationLevel, is_highest: true }] : [],
      employment: {
        employment_status: optional(values.employmentStatus), current_occupation: optional(values.currentOccupation),
        sector_code: optional(values.sector), industry_code: optional(values.industry),
        job_role: optional(values.jobRole), job_type: optional(values.jobType),
        work_region_code: optional(values.workRegion), work_district_code: optional(values.workDistrict),
        work_community: optional(values.workCommunity), skills: [], experience: []
      },
      sensitive: {
        current_income_amount: income, income_frequency: optional(values.incomeFrequency)?.toUpperCase() || null,
        disability_status: optional(values.disabilityStatus), disability_specify: optional(values.disabilitySpecify),
        refugee_status: optional(values.refugeeStatus), displacement_status: optional(values.displacementStatus)
      },
      implementing_partner: optional(values.implementingPartner), supplemental,
      training_summary: Object.keys(training).length ? JSON.stringify(training) : null,
      consent: { accepted: true, notice_version: noticeVersion }, reviewed: true, website: ''
    };
  }
  function validate(values) {
    const missing = [];
    [['firstName', 'First Name'], ['surname', 'Surname'], ['telephone', 'Phone Number'],
      ['community', 'Community']].forEach(([key, label]) => { if (!optional(values[key])) missing.push(label); });
    if (values.telephone && !/^(?:\+?233|0)[235]\d{8}$/.test(values.telephone.replace(/[\s()-]/g, ''))) missing.push('Valid Ghana Phone Number');
    if (values.dob && (values.dob > new Date().toISOString().slice(0, 10) || values.dob < '1900-01-01')) missing.push('Valid Date of Birth');
    return missing;
  }
  const api = { buildPayload, validate };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HamisIntake = api;
}(typeof window === 'undefined' ? globalThis : window));
