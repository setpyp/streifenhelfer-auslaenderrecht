// Bewertet einen Fall mit dem Regelwerk der App (app/regelwerk.js) – wie tests/run_tests.mjs.
// Eingabe: Fall-JSON auf stdin (Felder wie collect() in app/index.html, sonder = {id, erfuellt, offen}).
// Ausgabe: Bewertung als JSON auf stdout.
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = p => fs.readFileSync(path.join(root, p), "utf8");

const ctx = vm.createContext({});
vm.runInContext(read("app/regelwerk.js"), ctx, { filename: "regelwerk.js" });
const evaluate = vm.runInContext("evaluate", ctx);

const laender = JSON.parse(read("daten/laender.json")).kategorien;
const sonder = JSON.parse(read("daten/sonderregelungen.json")).regeln;
const catOf = name => Object.entries(laender).find(([, l]) => l.includes(name))?.[0] ?? "X";
const toDate = v => (v ? new Date(v + "T00:00:00") : null);

const s = JSON.parse(fs.readFileSync(0, "utf8"));
for (const k of ["date", "validUntil", "entryDE"]) s[k] = toDate(s[k]);
s.cat = catOf(s.nat);
s.sonderVerfuegbar = ["DE", "EU", "EUN", "EWR", "CH"].includes(s.cat) || !s.nat ? []
  : sonder.filter(x => x.staaten.includes("*") || x.staaten.includes(s.nat)).map(x => x.id);
if (s.sonder) s.sonder = { ...s.sonder, regel: sonder.find(x => x.id === s.sonder.id) };
process.stdout.write(JSON.stringify(evaluate(s)));
