// Regressionstests für das Regelwerk (app/regelwerk.js) gegen tests/faelle.json.
// Aufruf: node tests/run_tests.mjs        (Exit-Code 1 bei Fehlern)
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = p => fs.readFileSync(path.join(root, p), "utf8");

const ctx = vm.createContext({ console });
vm.runInContext(read("app/regelwerk.js"), ctx, { filename: "regelwerk.js" });
const evaluate = vm.runInContext("evaluate", ctx);

const laender = JSON.parse(read("daten/laender.json")).kategorien;
const catOf = name => Object.entries(laender).find(([, l]) => l.includes(name))?.[0] ?? "X";
const toDate = v => (v ? new Date(v + "T00:00:00") : null);

const { standard, faelle } = JSON.parse(read("tests/faelle.json"));
const checks = [
  ["feststellungen", "find"], ["massnahmen", "meas"], ["strafrecht", "crim"],
  ["benachrichtigungen", "notify"], ["hinweise", "notes"],
];

let failed = 0;
for (const f of faelle) {
  const s = { ...standard, ...f.eingabe };
  for (const k of ["date", "validUntil", "entryDE"]) s[k] = toDate(s[k]);
  s.cat = catOf(s.nat);
  const R = evaluate(s);
  const errs = [];
  const e = f.erwartet;
  if (e.level && R.level !== e.level) errs.push(`level: erwartet ${e.level}, ist ${R.level}`);
  if (e.head && R.head !== e.head) errs.push(`head: erwartet "${e.head}", ist "${R.head}"`);
  for (const [key, part] of checks) {
    const titles = R[part].map(i => i.t);
    for (const want of e[key] || []) if (!titles.some(t => t.includes(want))) errs.push(`${key}: fehlt "${want}" (vorhanden: ${titles.join(" | ") || "–"})`);
    for (const bad of e[key + "_nicht"] || []) if (titles.some(t => t.includes(bad))) errs.push(`${key}: darf "${bad}" nicht enthalten`);
  }
  // jede Aussage braucht mindestens ein Normzitat (außer reinen Statusmeldungen)
  for (const part of ["find", "meas", "crim", "notify"]) for (const i of R[part]) if (!i.n?.length) errs.push(`ohne Normzitat: "${i.t}"`);
  if (errs.length) { failed++; console.log(`✗ ${f.name}\n   - ${errs.join("\n   - ")}`); }
  else console.log(`✓ ${f.name}`);
}
console.log(`\n${faelle.length - failed}/${faelle.length} Fälle bestanden`);
process.exit(failed ? 1 : 0);
