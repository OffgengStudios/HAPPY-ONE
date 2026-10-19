import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const application = process.argv[2];
if (!['hamis', 'employer'].includes(application)) throw new Error('Choose hamis or employer.');
const source = application === 'hamis' ? 'frontend' : 'portal';
const output = path.join(root, source, 'dist');
const origin = process.env.HAPPY_API_BASE_URL || '';
if (origin) {
  const parsed = new URL(origin);
  if (parsed.pathname !== '/' || parsed.username || parsed.password || parsed.search || parsed.hash || !['http:', 'https:'].includes(parsed.protocol)) throw new Error('Use a public API origin without credentials or a path.');
  if (parsed.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(parsed.hostname)) throw new Error('Remote API origins require HTTPS.');
}
await mkdir(output, { recursive: true });
const html = await readFile(path.join(root, source, application === 'hamis' ? 'index.html' : 'src/intake.html'));
await writeFile(path.join(output, 'index.html'), html);
const files = application === 'hamis'
  ? ['js/utils.js', 'js/router.js', 'js/form-controls.js', 'js/intake-contract.js', 'js/public-intake.js']
  : ['src/styles.css', 'src/contract.js', 'src/app.js', 'assets/jobberman-logo.jpeg', 'assets/mastercard-foundation.webp'];
for (const file of files) {
  await mkdir(path.dirname(path.join(output, file)), { recursive: true });
  await cp(path.join(root, source, file), path.join(output, file));
}
const config = application === 'hamis' ? 'js/config.js' : 'src/config.js';
await mkdir(path.dirname(path.join(output, config)), { recursive: true });
await writeFile(path.join(output, config), 'window.HAPPY_API_BASE_URL = ' + JSON.stringify(origin) + ';\n');
console.log('Built ' + application + ' intake in ' + source + '/dist.');
