const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const hamis = require('../frontend/js/intake-contract.js');
const employer = require('../portal/src/contract.js');

test('HAMIS maps self-reported fields and never sends programme decisions', () => {
  const result = hamis.buildPayload({firstName:'Synthetic',surname:'Person',telephone:'0241234567',community:'Accra',ghanaCardId:'not-collected',readiness_status:'JOB_READY'}, {}, 'SYNTHETIC-1', '00000000-0000-4000-8000-000000000001');
  assert.equal(result.contact.phone_raw, '0241234567');
  assert.equal(result.consent.accepted, true);
  assert.equal(result.basic.first_name,'Synthetic');
  assert.ok(!JSON.stringify(result).includes('not-collected'));
  assert.ok(!JSON.stringify(result).includes('JOB_READY'));
});
test('HAMIS validates minimum intake and Ghana phone', () => {
  assert.equal(hamis.validate({firstName:'Synthetic',surname:'Person',telephone:'+233241234567',community:'Accra'}).length,0);
  assert.ok(hamis.validate({telephone:'bad'}).includes('Valid Ghana Phone Number'));
});
test('employer client preserves requirements and vacancy terms', () => {
  const result = employer.buildPayload({company_name:'Synthetic',consent_agreement:true,consent_contact:true},[{job_title:'Role',location:'Tema',employment_type:'FULL_TIME',openings:'2',skills:'Excel\nCustomer service',benefits:'Transport',accommodation:'yes'}],[], '00000000-0000-4000-8000-000000000002');
  assert.equal(result.vacancies[0].openings,2);
  assert.equal(result.vacancies[0].requirements.length,2);
  assert.deepEqual(result.vacancies[0].benefits,['Transport']);
  assert.equal(result.vacancies[0].accommodation,true);
  assert.ok(!JSON.stringify(result).includes('ACTIVE'));
});
for (const [directory, file] of [['frontend','index.html'], ['portal','index.html']]) {
  test(directory + ' active HTML references maintained local assets', () => {
    const html = fs.readFileSync(path.join(__dirname,'..',directory,file),'utf8');
    for (const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)) {
      if (/^(?:https?:|data:)/.test(match[1])) continue;
      assert.ok(fs.existsSync(path.join(__dirname,'..',directory,match[1])), match[1]);
    }
    assert.ok(!html.includes('script.google.com'));
    assert.ok(!html.includes('js/state-manager.js'));
  });
}
