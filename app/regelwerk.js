"use strict";
/* =====================================================================
   REGELWERK – reine Funktionen ohne DOM-Zugriff (testbar mit tests/run_tests.mjs).
   Eingabe: Sachverhalt s (siehe collect() in index.html), Ausgabe: Bewertung R.
   Jede Aussage: (Stufe, Titel, Erläuterung, [Normzitate], verifizieren?)
   Normzitate werden von tools/build_rechtsdaten.py gegen die amtlichen Texte geprüft.
   ===================================================================== */
const CAT_LABEL = {DE:"Deutsche/r",EU:"Unionsbürger/in (Schengen)",EUN:"Unionsbürger/in (Nicht-Schengen)",EWR:"EWR-Staatsangehörige/r",CH:"Schweizer/in",V:"Drittstaat – visumfrei (Anhang II)",VB:"Drittstaat – visumfrei mit biometrischem Pass",P:"Drittstaat – visumpflichtig (Anhang I)",X:"staatenlos/ungeklärt – wie visumpflichtig behandeln"};

function evaluate(s){
  const R = {level:"info", head:"", sub:"", find:[], meas:[], crim:[], notify:[], notes:[], path:[]};
  const mk = arr => (lvl,t,txt,n=[],v=false)=>arr.push({lvl,t,txt,n,v});
  const F=mk(R.find), M=mk(R.meas), C=mk(R.crim);
  const N=(t,txt,n=[],v=false)=>R.notify.push({lvl:"info",t,txt,n,v});
  const H=(t,txt,n=[],v=false)=>R.notes.push({lvl:"info",t,txt,n,v});
  const P=t=>R.path.push(t);

  const atBorderEntry = ["internal_border","external_border"].includes(s.place);
  const isExit = s.place==="exit";
  const minor = s.age!==null && s.age<18;

  if(!s.place){ R.level="warn"; R.head="Ort/Lage der Kontrolle fehlt"; R.sub="Bitte unter 1 · Kontrollsituation auswählen."; return R; }
  if(!s.nat){ R.level="warn"; R.head="Staatsangehörigkeit fehlt"; R.sub="Bitte Staatsangehörigkeit (ggf. „ungeklärt“) auswählen."; return R; }

  /* ---- Rechtsgrundlage der Kontrolle ---- */
  const ctrlBasis = {
    internal_border:["Grenzkontrolle bei vorübergehend wiedereingeführten Binnengrenzkontrollen",["Art. 25, 32 SGK","§ 2 Abs. 2 Nr. 1 BPolG","§ 13 AufenthG"]],
    external_border:["Grenzübertrittskontrolle an der Außengrenze",["Art. 8 SGK","§ 2 Abs. 2 Nr. 1 BPolG","§ 13 AufenthG","Art. 6 EES-VO"]],
    border_area:["Identitätsfeststellung im Grenzgebiet (30 km)",["§ 23 Abs. 1 Nr. 3 BPolG","Art. 23 SGK"]],
    rail:["Befragung/Identitätsfeststellung Bahnanlagen",["§ 22 Abs. 1a BPolG","§ 23 Abs. 1 Nr. 4 BPolG","§ 3 BPolG"]],
    airport_inland:["Befragung im Flughafen (Schengen-Binnenflug)",["§ 22 Abs. 1a BPolG","§ 4 BPolG"]],
    exit:["Ausreisekontrolle",["Art. 8 Abs. 3 SGK","§ 13 AufenthG"]],
    inland:["Kontrolle im Inland – Zuständigkeit prüfen",["§ 1 BPolG","§ 64 BPolG"]]
  }[s.place];
  M("info","Rechtsgrundlage der Kontrolle: "+ctrlBasis[0],"Anlassunabhängige Kontrollen diskriminierungsfrei durchführen (keine Auswahl allein nach Hautfarbe/Herkunft); Lageerkenntnisse dokumentieren. Kontrollen im Binnengrenzgebiet dürfen nicht die gleiche Wirkung wie Grenzübertrittskontrollen haben.",[...ctrlBasis[1],"Art. 3 Abs. 3 GG"], !atBorderEntry && !isExit);

  if(s.warrant) M("bad","Fahndungstreffer abarbeiten","Maßnahme nach Ausschreibungsinhalt (Festnahme, Aufenthaltsermittlung, Einreiseverweigerung); Belehrung, Vorführung, Benachrichtigungen.",["§ 127 StPO","§ 457 StPO","Art. 26 2018/1862"]);

  /* ================= Deutsche ================= */
  if(s.cat==="DE"){
    P("Deutsche Staatsangehörigkeit → kein Ausländer i.S.d. AufenthG.");
    R.level="ok"; R.head="Deutsche/r Staatsangehörige/r"; R.sub="Aufenthaltsrecht kraft Staatsangehörigkeit. AufenthG nicht anwendbar.";
    F("ok","Kein Ausländer","Auch bei Mehrstaatigkeit gilt die Person als Deutsche/r.",["§ 2 Abs. 1 AufenthG","Art. 116 Abs. 1 GG"]);
    if(["none","expired"].includes(s.iddoc)) F("warn","Ausweis-/Passpflicht","Pflicht zum Besitz, nicht zum Mitführen im Inland. Beim Grenzübertritt über eine Auslandsgrenze Pass oder Personalausweis erforderlich.",["§ 1 PAuswG","§ 1 PassG","§ 32 PAuswG","§ 25 PassG"],true);
    M("info","Identitätsfeststellung","Bei fehlendem Dokument Identität anderweitig feststellen.",["§ 23 Abs. 3 BPolG","§ 24 BPolG"]);
    return R;
  }

  /* ================= Freizügigkeitsberechtigte ================= */
  if(["EU","EUN","EWR","CH"].includes(s.cat)){
    P("Unionsbürger/EWR/CH → FreizügG/EU bzw. FZA; kein Aufenthaltstitel erforderlich.");
    R.level="ok"; R.head="Freizügigkeitsberechtigt (vermutet)"; R.sub="Recht auf Einreise und Aufenthalt nach FreizügG/EU; Verlust nur durch Feststellung der Ausländerbehörde.";
    F("ok","Freizügigkeitsvermutung","Bis 3 Monate voraussetzungsloses Aufenthaltsrecht; danach Vermutung der Freizügigkeit, solange keine Verlustfeststellung vorliegt.",["§ 2 Abs. 1, 5 FreizügG/EU","§ 7 Abs. 1 FreizügG/EU","Art. 6, 7 2004/38", s.cat==="CH"?"FZA":"§ 12 FreizügG/EU"]);
    if(["none","expired","forged"].includes(s.iddoc)){
      F("warn","Kein gültiges Ausweisdokument","Einreise darf nicht allein wegen fehlenden Dokuments verweigert werden, wenn Identität und Staatsangehörigkeit anderweitig nachgewiesen werden können (angemessene Gelegenheit geben).",["Art. 5 Abs. 4 2004/38","§ 8 Abs. 1 FreizügG/EU"]);
      C("warn","Ordnungswidrigkeit Ausweispflicht","Nichtvorlage bei Ein-/Ausreise bzw. auf Verlangen (Abs. 1); Nichtbesitz vorsätzlich/leichtfertig (Abs. 2).",["§ 10 Abs. 1, 2 FreizügG/EU"]);
      if(s.iddoc==="forged") C("bad","Urkundendelikt prüfen","Sicherstellung des Dokuments, Strafanzeige.",["§§ 267, 273, 276, 281 StGB","§ 94 StPO"]);
    }
    if(s.sisRefusal){
      R.level="bad"; R.head="Einreise-/Aufenthaltsverbot (FreizügG/EU) prüfen";
      F("bad","Verlustfeststellung mit Einreise- und Aufenthaltsverbot?","Nur wirksam bei Verlustfeststellung aus Gründen der öffentlichen Ordnung, Sicherheit oder Gesundheit (bzw. Nichtbestehensfeststellung) und Untersagung der Wiedereinreise.",["§ 6 FreizügG/EU","§ 7 Abs. 2 FreizügG/EU"]);
      C("bad","Einreise/Aufenthalt trotz Verbot","Strafbar, wenn Verbot wirksam und bekanntgegeben.",["§ 9 Abs. 2 FreizügG/EU"]);
      if(atBorderEntry) M("bad","Zurückweisung","Bei wirksamem Einreise- und Aufenthaltsverbot – Rechtsgrundlage/Verfahren nach Weisungslage.",["§ 7 Abs. 2 FreizügG/EU","§ 11 FreizügG/EU"],true);
    }
    if(s.cat==="EUN" && s.place==="internal_border") H("Irland/Zypern","Nicht Schengen: Einreise aus diesen Staaten ist Außengrenzübertritt, Kontrolle nach Art. 8 Abs. 2 SGK.",["Art. 8 Abs. 2 SGK"]);
    if(s.nomeans) H("Fehlende Existenzmittel","Kein Grund für polizeiliche Maßnahmen; ggf. Mitteilung an Ausländerbehörde zur Prüfung.",["§ 5 Abs. 4 FreizügG/EU"]);
    commonTail(s,R,{M,N,H,P,minor,lawful:true});
    return R;
  }

  /* ================= Drittstaatsangehörige ================= */
  P("Drittstaatsangehörige/r ("+CAT_LABEL[s.cat]+") → AufenthG, SGK, VO (EU) 2018/1806.");
  const visaFree = s.cat==="V" || (s.cat==="VB" && s.iddoc==="pass");
  const passOK = ["pass","pass_nonbio","passersatz"].includes(s.iddoc);
  const validTitle = s.validUntil ? s.validUntil >= s.date : true;
  const dayOK = s.days===null ? null : s.days<=90;
  let lawful = null, unlawfulEntry = false, basis = "";

  /* -- Pass -- */
  if(!passOK){
    F("bad","Passpflicht nicht erfüllt","Ausländer müssen einen gültigen und anerkannten Pass oder Passersatz besitzen.",["§ 3 Abs. 1 AufenthG","§ 48 Abs. 2 AufenthG"]);
    if(s.title==="gestattung") F("info","Ausweispflicht durch Gestattung/Ankunftsnachweis erfüllt","Die Bescheinigung berechtigt nicht zum Grenzübertritt.",["§ 64 AsylG"]);
    if(s.title==="duldung") F("info","Duldung als Ausweisersatz","Nur wenn als Ausweisersatz bezeichnet und mit Lichtbild versehen.",["§ 48 Abs. 2 AufenthG","§ 55 AufenthV"]);
    if(s.iddoc==="forged") C("bad","Urkundendelikt / Fälschungsverdacht","Dokument sicherstellen, Urkundenprüfung, Strafanzeige; ED-Behandlung soll erfolgen.",["§§ 267, 273, 276, 281 StGB","§ 94 StPO","§ 49 Abs. 5 AufenthG"]);
  } else if(s.cat==="VB" && s.iddoc==="pass_nonbio"){
    F("bad","Visumfreiheit nur mit biometrischem Pass","Mit nicht-biometrischem Pass besteht Visumpflicht.",["Anhang II 2018/1806"]);
  }

  /* -- Sonderregelungen (daten/sonderregelungen.json): Befreiungen außerhalb der Visumliste -- */
  const SR = s.sonder ? s.sonder.regel : null;
  const sonderOK = !!(SR && SR.typ==="befreiung" && s.sonder.erfuellt);
  if(SR && SR.typ==="hinweis") H(SR.titel, SR.rechtsfolge+(SR.hinweise?" "+SR.hinweise:""), SR.quellen, !SR.verifiziert);
  if(SR && SR.typ==="befreiung" && !sonderOK)
    F("warn","Befreiung nicht anwendbar: "+SR.titel,"Voraussetzungen nicht (vollständig) bestätigt: "+(s.sonder.offen||[]).join("; ")+". Bewertung nach allgemeinen Regeln.",SR.quellen,!SR.verifiziert);

  /* -- Aufenthaltsgrundlage -- */
  if(sonderOK){
    basis="Befreiung: "+SR.titel; lawful = passOK;
    F(lawful?"ok":"bad","Befreiung: "+SR.titel, SR.rechtsfolge+(lawful?"":" Passpflicht ist dennoch zu erfüllen."), SR.quellen, !SR.verifiziert);
    H("Geltungsbereich der Befreiung", SR.geltungsbereich, SR.quellen, !SR.verifiziert);
    if(SR.hinweise) H("Hinweise zur Befreiung", SR.hinweise, SR.quellen, !SR.verifiziert);
    P("Sonderregelung „"+SR.titel+"“: alle Voraussetzungen bestätigt.");
  } else switch(s.title){
    case "at_de":
      basis="Deutscher Aufenthaltstitel"; lawful = validTitle;
      if(lawful) F("ok","Gültiger deutscher Aufenthaltstitel","Aufenthalt rechtmäßig. Nebenbestimmungen (Erwerbstätigkeit, Wohnsitzauflage) prüfen.",["§ 4 Abs. 1 AufenthG","§ 4a AufenthG","§ 12 AufenthG","§ 12a AufenthG"]);
      else { F("warn","Aufenthaltstitel abgelaufen","Rechtmäßigkeit hängt von rechtzeitigem Verlängerungsantrag ab (Fortgeltungsfiktion). AZR-Abfrage / Ausländerbehörde.",["§ 81 Abs. 4 AufenthG","§ 51 Abs. 1 Nr. 1 AufenthG","§ 58 Abs. 2 AufenthG"]); lawful=null; }
      break;
    case "visa_d_de":
      basis="Nationales Visum DE"; lawful = validTitle;
      F(lawful?"ok":"bad", lawful?"Gültiges nationales Visum (DE)":"Nationales Visum abgelaufen", lawful?"Berechtigt zum Aufenthalt nach Visumzweck.":"Ohne Fiktionsbescheinigung/Antrag: unerlaubter Aufenthalt.",["§ 6 Abs. 3 AufenthG","§ 81 Abs. 4 AufenthG"]);
      break;
    case "visa_d_other":
    case "at_other":
      basis = s.title==="at_other" ? "Aufenthaltstitel anderer Schengen-Staat" : "Nationales Visum anderer Schengen-Staat";
      if(!validTitle){ lawful=false; F("bad",basis+" abgelaufen","Kein Recht zur Einreise/zum Aufenthalt in Deutschland.",["Art. 21 SDÜ"]); }
      else if(dayOK===false){ lawful=false; F("bad","90/180-Tage überschritten","Kurzaufenthalt nach Art. 21 SDÜ nur bis 90 Tage je 180 Tage.",["Art. 21 SDÜ","Art. 6 Abs. 1 SGK"]); }
      else { lawful = passOK ? (dayOK===null?null:true) : false; if(lawful===null) R.dauerRelevant=true;
        F(lawful===false?"bad":(lawful?"ok":"warn"),"Kurzaufenthalt nach Art. 21 SDÜ","Bis 90 Tage je 180 Tage bei gültigem Reisedokument; keine Erwerbstätigkeit (Ausnahmen § 17 Abs. 2, 3 AufenthV).",["Art. 21 SDÜ","Art. 6 Abs. 1 SGK","§ 15 AufenthV","§ 17 AufenthV"]); }
      break;
    case "visa_c":
    case "visa_ltv":
      basis="Schengen-Visum";
      if(s.title==="visa_ltv" && !s.ltvDE){ lawful=false; F("bad","VrG/LTV-Visum nicht für Deutschland gültig","Visum berechtigt nur zum Aufenthalt in den genannten Staaten.",["Art. 25 Visakodex"]); break; }
      if(!validTitle){ lawful=false; F("bad","Visum abgelaufen (Overstay)","Gültigkeitsdauer überschritten.",["Art. 6 SGK","§ 4 Abs. 1 AufenthG"]); }
      else if(s.days!==null && s.days > s.visaDays){ lawful=false; F("bad","Zulässige Aufenthaltsdauer des Visums überschritten",`${s.days} Tage genutzt, ${s.visaDays} erlaubt.`,["Art. 24 Visakodex","§ 4 Abs. 1 AufenthG"]); }
      else { lawful = passOK ? (s.days===null?null:true) : false; if(lawful===null) R.dauerRelevant=true;
        F(lawful===false?"bad":(lawful?"ok":"warn"),"Gültiges Schengen-Visum","Nur Kurzaufenthalt zum Visumzweck; Erwerbstätigkeit grds. nicht gestattet. VIS-Abfrage empfohlen.",["§ 6 Abs. 1 Nr. 1 AufenthG","Art. 24 Visakodex","Art. 18 VIS-VO"]);
        if(s.purpose==="work"||s.purpose==="family"||s.working) F("warn","Zweckwidrigkeit","Annullierung/Aufhebung des Visums durch die Grenzbehörde im Zusammenhang mit Zurückweisung/Zurückschiebung/Abschiebung möglich.",["Art. 34 Visakodex","§ 71 Abs. 3 Nr. 3 AufenthG"]);
      }
      break;
    case "fiktion":
      basis="Fiktionsbescheinigung"; lawful = validTitle?true:null;
      F(lawful?"ok":"warn","Fiktionsbescheinigung","Aufenthalt gilt als erlaubt / Abschiebung als ausgesetzt / Titel als fortbestehend – Art der Fiktion (Abs. 3 S. 1, S. 2 oder Abs. 4) auf der Bescheinigung beachten!",["§ 81 Abs. 3, 4, 5 AufenthG"]);
      break;
    case "p24":
      basis="Vorübergehender Schutz"; lawful = validTitle?true:null;
      F(lawful?"ok":"warn","Vorübergehender Schutz","Aufenthalt rechtmäßig; Erwerbstätigkeit erlaubt.",["§ 24 AufenthG","2001/55","2022/382"],true);
      break;
    case "gestattung":
      basis="Aufenthaltsgestattung"; lawful=true;
      F("ok","Aufenthaltsgestattung","Aufenthalt zur Durchführung des Asylverfahrens gestattet.",["§ 55 AsylG","§ 63 AsylG"]);
      if(s.restrictViol){
        F("warn","Räumliche Beschränkung","Verstoß gegen räumliche Beschränkung (§ 56, § 59b Abs. 1 AsylG): erstmalig OWi, wiederholt Straftat. Erlöschen nach 3 Monaten beachten (§ 59a AsylG).",["§ 56 AsylG","§ 59a AsylG","§ 59b AsylG"]);
        if(s.restrictRepeat) C("bad","Wiederholter Verstoß gegen Aufenthaltsbeschränkung","Straftat.",["§ 85 Nr. 2 AsylG"]);
        else C("warn","Verstoß gegen Aufenthaltsbeschränkung","Ordnungswidrigkeit.",["§ 86 Abs. 1 Nr. 2 AsylG"]);
        M("warn","Durchsetzung der Verlassenspflicht","Ggf. unmittelbarer Zwang; Reiseweg vorschreiben; Haft nur auf richterliche Anordnung.",["§ 59 Abs. 1, 2 AsylG","§ 12 Abs. 3 AufenthG"]);
      }
      if(isExit) H("Ausreise während Asylverfahren","Bescheinigung über die Gestattung berechtigt nicht zum Grenzübertritt. Ausreise kann als stillschweigende Rücknahme des Antrags gewertet werden – Mitteilung an BAMF.",["§ 64 Abs. 2 AsylG","Art. 41 APR"],true);
      break;
    case "duldung":
      basis="Duldung"; lawful=false;
      F("warn","Duldung – ausreisepflichtig, Abschiebung ausgesetzt","Kein rechtmäßiger Aufenthalt, aber keine Strafbarkeit nach § 95 Abs. 1 Nr. 2 AufenthG bei gültiger Duldung (Buchst. c).",["§ 60a AufenthG","§ 50 AufenthG","§ 95 Abs. 1 Nr. 2 AufenthG"]);
      if(s.restrictViol){
        if(s.restrictRepeat) C("bad","Wiederholter Verstoß gegen räumliche Beschränkung","Straftat.",["§ 95 Abs. 1 Nr. 7 AufenthG","§ 61 Abs. 1 AufenthG"]);
        else C("warn","Verstoß gegen räumliche Beschränkung","Ordnungswidrigkeit.",["§ 98 Abs. 3 Nr. 5b AufenthG","§ 61 Abs. 1 AufenthG"]);
      }
      if(!validTitle) F("bad","Duldung abgelaufen","Vollziehbare Ausreisepflicht ohne Aussetzung – Ausländerbehörde kontaktieren.",["§ 58 AufenthG"]);
      if(isExit) H("Ausreise mit Duldung","Aussetzung der Abschiebung erlischt mit der Ausreise; Ausreise dokumentieren, Mitteilung an Ausländerbehörde.",["§ 60a Abs. 5 AufenthG","§ 87 Abs. 2 AufenthG"]);
      if(atBorderEntry) F("bad","Wiedereinreise mit Duldung","Duldung ist mit der Ausreise erloschen – Einreise ohne erforderlichen Titel.",["§ 60a Abs. 5 AufenthG","§ 14 Abs. 1 AufenthG"]);
      break;
    case "eu_card":
    case "grenzgaenger":
      basis="Familienangehöriger Unionsbürger"; lawful = validTitle?true:null;
      F(lawful?"ok":"warn","Aufenthaltskarte EU-Familienangehöriger","Befreit von der Visumpflicht; Aufenthaltsrecht abgeleitet vom Unionsbürger.",["Art. 5 Abs. 2, Art. 10, 20 2004/38","§ 2 Abs. 4 FreizügG/EU","§ 3 FreizügG/EU","§ 5 FreizügG/EU"]);
      break;
    default:
      if(s.eufam){
        basis="Familienangehöriger Unionsbürger ohne Karte"; lawful=null;
        F("warn","EU-Familienangehöriger ohne Aufenthaltskarte","Visumpflicht nach Anhang I, aber jede Erleichterung zu gewähren; Nachweis der Familienangehörigkeit auf andere Weise zulassen.",["Art. 5 Abs. 2, 4 2004/38","§ 2 Abs. 4 FreizügG/EU"]);
      } else if(visaFree){
        basis="Visumfreier Kurzaufenthalt";
        if(dayOK===false){ lawful=false; F("bad","90/180-Tage überschritten (Overstay)",`${s.days} Tage im Bezugszeitraum.`,["Art. 6 Abs. 1 SGK","Art. 20 SDÜ","Art. 4 2018/1806"]);
          if((s.sonderVerfuegbar||[]).includes("anlage-a-sichtvermerk")) H("Ältere Sichtvermerksabkommen","Für diese Staatsangehörigkeit besteht ein älteres Sichtvermerksabkommen (Anlage A AufenthV), das längere Aufenthalte in Deutschland erlauben kann – unter „Sonderstatus“ prüfen.",["§ 16 AufenthV","AufenthV Anlage A","Art. 20 SDÜ"]); }
        else { lawful = passOK ? (dayOK===null?null:true) : false; if(lawful===null) R.dauerRelevant=true;
          F(lawful===false?"bad":(lawful?"ok":"warn"),"Visumfreier Kurzaufenthalt","Bis 90 Tage je 180 Tage; Einreisevoraussetzungen Art. 6 SGK (Zweck, Mittel, keine Ausschreibung). Nach Inbetriebnahme von ETIAS zusätzlich gültige Reisegenehmigung erforderlich.",["Art. 4 2018/1806","Art. 6 SGK","Art. 20 SDÜ","§ 15 AufenthV","ETIAS-VO"],true);
          if(dayOK===null) H("Aufenthaltsdauer unbekannt","Ein-/Ausreisestempel bzw. EES-Abfrage zur Berechnung heranziehen.",["Art. 6 Abs. 2 SGK","EES-VO"]);
        }
      } else {
        basis="Kein Titel, visumpflichtig"; lawful=false;
        F("bad","Erforderlicher Aufenthaltstitel fehlt","Visumpflichtige/r Drittstaatsangehörige/r ohne Visum oder Aufenthaltstitel.",["§ 4 Abs. 1 AufenthG","Art. 3 2018/1806"]);
      }
  }
  P("Aufenthaltsgrundlage: "+(basis||"–")+" → "+(lawful===true?"rechtmäßig":lawful===false?"nicht rechtmäßig":"ungeklärt"));
  if(!passOK && s.title!=="gestattung" && s.title!=="duldung" && lawful===true){ lawful=false; P("Ohne gültigen Pass → Einreise-/Aufenthaltsvoraussetzungen nicht erfüllt."); }

  /* Erwerbstätigkeit */
  if(s.working && ["visa_c","visa_ltv","at_other","visa_d_other","none"].includes(s.title) && !s.eufam && !(sonderOK && SR.erwerbstaetigkeit_erlaubt)){
    F("bad","Unerlaubte Erwerbstätigkeit möglich","Kurzaufenthalt/Visum berechtigt grds. nicht zur Erwerbstätigkeit; Ausnahmen § 17 Abs. 2, 3 AufenthV i.V.m. § 30 BeschV prüfen.",["§ 4a Abs. 1, 5 AufenthG","§ 17 AufenthV","§ 30 BeschV"]);
    if(s.title==="visa_c"||s.title==="visa_ltv") C("bad","Unerlaubte Beschäftigung mit Schengen-Visum","Vorsätzliche Begehung ist Straftat.",["§ 95 Abs. 1a AufenthG","§ 404 Abs. 2 Nr. 4 SGB III"]);
    else C("warn","Unerlaubte Beschäftigung / selbständige Tätigkeit","Beschäftigung: OWi nach SGB III; selbständige Tätigkeit: OWi nach AufenthG.",["§ 404 Abs. 2 Nr. 4 SGB III","§ 98 Abs. 3 Nr. 1 AufenthG"]);
    N("Finanzkontrolle Schwarzarbeit (Zoll)","Mitteilung zur Prüfung der Beschäftigung (auch Arbeitgeberhaftung).",["§ 6 SchwarzArbG","§ 66 Abs. 4 AufenthG"],true);
    if(atBorderEntry) M("warn","Zurückweisung wegen beabsichtigter Erwerbstätigkeit","Kann-Zurückweisung bei Schengen-Visum/Visumfreiheit und beabsichtigter unerlaubter Erwerbstätigkeit.",["§ 15 Abs. 2 AufenthG"]);
  }

  /* SIS / Einreiseverbot */
  if(s.sisRefusal){
    lawful=false;
    F("bad","Einreise- und Aufenthaltsverbot / SIS-Ausschreibung","Titel/Befreiung entfällt; Einreise und Aufenthalt nicht erlaubt.",["§ 11 Abs. 1 AufenthG","Art. 24 2018/1861","Art. 6 Abs. 1 SGK"]);
    C("bad","Einreise/Aufenthalt trotz Einreiseverbot","Strafbar; Versuch der Einreise strafbar.",["§ 95 Abs. 2 Nr. 1 AufenthG","§ 95 Abs. 3 AufenthG"]);
  }
  if(s.nomeans && lawful!==false && (s.title==="visa_c"||s.title==="none"))
    F("warn","Einreisevoraussetzung Mittel fraglich","Fehlende Mittel können zur Einreiseverweigerung führen (an der Grenze).",["Art. 6 Abs. 1 SGK","§ 15 Abs. 2 AufenthG","§ 5 Abs. 1 AufenthG"]);

  /* Unerlaubte Einreise */
  if(lawful===false && s.title!=="duldung" && s.title!=="gestattung"){
    if(atBorderEntry){ unlawfulEntry=true; P("Einreisekontrolle: Einreise wäre unerlaubt."); }
    else if(!isExit && ((s.title==="none"&&!visaFree&&!s.eufam) || !passOK || s.sisRefusal)){ unlawfulEntry=true; P("Einreise ohne erforderlichen Pass/Titel bzw. trotz Verbot → unerlaubte Einreise (§ 14 Abs. 1 AufenthG)."); }
  }

  /* ================= Asyl ================= */
  if(s.asylum){
    P("Schutzgesuch geäußert → asylrechtliche Verfahrensregeln vorrangig; Refoulement-Verbot.");
    R.level="warn"; R.head="Asylsuchende/r"; R.sub="Schutzgesuch geäußert – Weiterleitung bzw. Prüfung nach §§ 18, 19 AsylG und GEAS.";
    F("warn","Schutzgesuch","Gesuch ist unabhängig von Form und Sprache beachtlich. Keine Maßnahme, die zur Zurückweisung in einen Verfolgerstaat führt.",["§ 13 AsylG","Art. 33 GFK","Art. 3 EMRK","Art. 18, 19 GRCh","§ 15 Abs. 4 AufenthG"]);
    if(atBorderEntry){
      M("warn","Einreiseverweigerung nach § 18 Abs. 2 AsylG prüfen","Einreise ist zu verweigern bei Einreise aus sicherem Drittstaat (§ 26a AsylG), bei Anhaltspunkten für Zuständigkeit eines anderen Staates mit eingeleitetem (Wieder-)Aufnahmeverfahren oder bei Gefahr für die Allgemeinheit; Ausnahmen § 18 Abs. 4 AsylG. Andernfalls Weiterleitung an Aufnahmeeinrichtung (ggf. nach Screening). Praxis bei Binnengrenzen rechtlich umstritten – aktuelle Weisungslage beachten.",["§ 18 Abs. 1, 2, 4 AsylG","AMMR","Screening-VO"],true);
      M("warn","Erkennungsdienstliche Behandlung","Pflicht der Grenzbehörde.",["§ 18 Abs. 5 AsylG","§ 16 AsylG","Eurodac"]);
      if(s.place==="external_border") M("warn","Screening / Asylgrenzverfahren","Überprüfung an der Außengrenze; ggf. Asylgrenzverfahren bzw. Flughafenverfahren.",["Art. 5 Screening-VO","§ 18a AsylG","Art. 43 APR"]);
    } else {
      M("warn","Weiterleitung an Aufnahmeeinrichtung","Unverzüglich an die zuständige bzw. nächstgelegene Aufnahmeeinrichtung weiterleiten; sofern erforderlich nach Abschluss der Überprüfung (Screening). Weiterleitung schriftlich mitteilen.",["§ 19 Abs. 1 AsylG","§ 20 AsylG","Screening-VO"]);
      M("warn","Erkennungsdienstliche Behandlung","Lichtbild und Fingerabdrücke (unter 6 Jahren nur Lichtbild).",["§ 16 Abs. 1 AsylG","§ 19 Abs. 2 AsylG","Eurodac"]);
      if(s.nearEntry && unlawfulEntry) M("warn","Zurückschiebung nach § 18 Abs. 3 AsylG prüfen","Bei Antreffen im grenznahen Raum in unmittelbarem zeitlichem Zusammenhang mit unerlaubter Einreise und Vorliegen der Voraussetzungen des § 18 Abs. 2 AsylG.",["§ 18 Abs. 3 AsylG","§ 71 Abs. 3 Nr. 1 AufenthG"],true);
    }
    C("info","Strafbarkeit unerlaubte Einreise bei Schutzsuchenden","Art. 31 Abs. 1 GFK bleibt unberührt (unmittelbare Einreise aus Verfolgerstaat, unverzügliche Meldung). Anzeige nach Weisungslage.",["§ 95 Abs. 5 AufenthG","Art. 31 GFK"]);
  }

  /* ================= Status ================= */
  if(!s.asylum){
    if(s.title==="duldung"){ R.level="warn"; R.head="Geduldet – ausreisepflichtig"; R.sub="Abschiebung vorübergehend ausgesetzt."; }
    else if(lawful===true && sonderOK && !SR.verifiziert){ R.level="warn"; R.head="Voraussichtlich rechtmäßig – Befreiung prüfen"; R.sub=basis+". Die Befreiung beruht auf Rechtsprechung/Verwaltungspraxis – aktuelle Weisungslage und Nachweise prüfen."; }
    else if(lawful===true){ R.level="ok"; R.head="Rechtmäßiger Aufenthalt"; R.sub=basis+". Einreise-/Aufenthaltsvoraussetzungen nach Aktenlage erfüllt."; }
    else if(lawful===null){ R.level="warn"; R.head="Status ungeklärt – weitere Prüfung"; R.sub=basis+". Fehlende Angaben (Aufenthaltsdauer, Gültigkeit, Antrag) klären."; }
    else if(isExit){ R.level="warn"; R.head="Unerlaubter Aufenthalt – Ausreise"; R.sub="Ausreise erfüllt die Ausreisepflicht; Verstöße dokumentieren."; }
    else if(atBorderEntry){ R.level="bad"; R.head="Einreisevoraussetzungen nicht erfüllt"; R.sub="Einreise wäre unerlaubt (§ 14 Abs. 1 AufenthG) – Zurückweisung."; }
    else { R.level="bad"; R.head = unlawfulEntry ? "Unerlaubte Einreise und unerlaubter Aufenthalt" : "Unerlaubter Aufenthalt"; R.sub="Ausreisepflichtig (§ 50 Abs. 1 AufenthG); vollziehbar insb. nach unerlaubter Einreise (§ 58 Abs. 2 AufenthG)."; }
  }

  /* ================= Maßnahmen Drittstaat ================= */
  if(lawful===false && !s.asylum && s.title!=="duldung"){
    if(atBorderEntry){
      M("bad","Zurückweisung / Einreiseverweigerung","Zurückweisung an der Grenze; Einreiseverweigerung mit Standardformular (Anhang V Teil B SGK) inkl. Begründung und Rechtsbehelfsbelehrung; Erfassung im EES.",["§ 15 Abs. 1 AufenthG","Art. 14 SGK","Art. 32 SGK","Art. 18 EES-VO"]);
      M("warn","Zurückweisungshaft","Wenn die Zurückweisung nicht unmittelbar vollzogen werden kann: richterliche Anordnung (Soll-Vorschrift). Flughafen: Transitbereich (§ 15 Abs. 6).",["§ 15 Abs. 5, 6 AufenthG","Art. 104 Abs. 2 GG"]);
      if(s.place==="internal_border") H("Transferverfahren","Bei Aufgriff im Binnengrenzgebiet im Rahmen bilateraler Zusammenarbeit: Überstellung an den Nachbarstaat möglich.",["Art. 23a SGK"],true);
    } else if(isExit){
      M("info","Ausreise zulassen und dokumentieren","Ausreise erfüllt die Ausreisepflicht. Overstay im EES erfassen; Mitteilung an Ausländerbehörde zur Prüfung eines Einreise- und Aufenthaltsverbots.",["Art. 8 Abs. 3 SGK","§ 50 AufenthG","§ 11 Abs. 6 AufenthG","§ 87 Abs. 2 AufenthG"]);
    } else {
      if(unlawfulEntry){
        if(s.from==="nonschengen") M("bad","Zurückschiebung (Außengrenze)","Wer in Verbindung mit der unerlaubten Einreise über eine Außengrenze aufgegriffen wird, soll zurückgeschoben werden.",["§ 57 Abs. 1 AufenthG","§ 71 Abs. 3 Nr. 1 AufenthG"]);
        M(s.nearEntry?"bad":"warn","Zurückschiebung in Mitgliedstaat / NO / CH prüfen","Soll-Zurückschiebung bei Wiederaufnahme aufgrund zwischenstaatlicher Übernahmevereinbarung; ebenso bei Antreffen im grenznahen Raum in unmittelbarem zeitlichen Zusammenhang mit unerlaubter Einreise, wenn ein anderer Staat für ein Asylverfahren zuständig ist und ein (Wieder-)Aufnahmeverfahren eingeleitet wird.",["§ 57 Abs. 2, 3 AufenthG","§ 71 Abs. 3 Nr. 1 AufenthG","Art. 6 Abs. 3 2008/115"]);
        if(!s.nearEntry) M("warn","Abschiebung durch BPol / Übergabe an Ausländerbehörde","Zuständigkeit der BPol für Abschiebungen bei Aufgriff bei/nach unerlaubter Einreise über Binnengrenze bzw. in anderem Grenzraum; sonst Ausländerbehörde (Abschiebungsandrohung).",["§ 71 Abs. 3 Nr. 1a, 1b AufenthG","§ 59 AufenthG","§ 71 Abs. 1 AufenthG"]);
        if(s.from!=="schengen") M("warn","Überprüfung (Screening) im Hoheitsgebiet prüfen","Bei Personen, die die Außengrenze irregulär überschritten haben und keiner Grenzkontrolle unterzogen wurden; zuständig BPol bei Feststellung in Erfüllung grenzpolizeilicher Aufgaben.",["Art. 7 Screening-VO","§ 71 Abs. 3 Nr. 9 AufenthG"],true);
      } else M("warn","Übergabe/Mitteilung an Ausländerbehörde","Aufenthaltsbeendigung durch Ausländerbehörde (Abschiebungsandrohung, Ausreisefrist).",["§ 59 AufenthG","§ 71 Abs. 1 AufenthG"]);
      M("warn","Festhalten / Sicherungshaft","Bei dringendem Verdacht der Haftvoraussetzungen und Entziehungsgefahr: vorläufige Ingewahrsamnahme ohne vorherige richterliche Anordnung; unverzüglich richterliche Entscheidung. Minderjährige grds. nicht.",["§ 62 Abs. 1, 3, 3a, 3b AufenthG","§ 62 Abs. 5 AufenthG","§ 71 Abs. 3 Nr. 1e AufenthG","§ 415 FamFG","Art. 104 GG"]);
      M("info","Sicherheitsleistung / Beschlagnahme Rückflugscheine","Zur Sicherung der Kosten von Zurückschiebung/Abschiebung; Durchsuchung nach Geldmitteln bei Anhaltspunkten.",["§ 66 Abs. 1, 5 AufenthG","§ 71 Abs. 3 Nr. 4 AufenthG"]);
    }
    M("warn","Pass und Urkunden in Verwahrung nehmen","Pass/Urkunden eines Ausreisepflichtigen sollen verwahrt werden; bei fehlendem Pass Durchsuchung nach Identitätspapieren und Datenträgern zulässig.",["§ 48 Abs. 1, 3 AufenthG","§ 50 Abs. 5 AufenthG"]);
    if(!atBorderEntry) M("warn","Erkennungsdienstliche Behandlung","Pflicht bei Aufgriff in Verbindung mit unerlaubter Einreise (Abs. 8) bzw. Aufenthalt ohne erforderlichen Titel (Abs. 9); unter 6 Jahren nur Lichtbild.",["§ 49 Abs. 8, 9 AufenthG","Eurodac"]);
    else M("info","Erkennungsdienstliche Behandlung bei Zurückweisung","Soll bei gefälschtem Pass, Verdacht erneuter unerlaubter Einreise oder Zurückweisung in sicheren Drittstaat.",["§ 49 Abs. 5 AufenthG"]);
  }
  if(lawful===null && !s.asylum){
    M("warn","Sachverhalt aufklären","AZR-, INPOL-, SIS-, VIS- und EES-Abfrage; Kontakt Ausländerbehörde (Verlängerungsantrag/Fiktion).",["§ 49 Abs. 2, 3 AufenthG","§ 23 BPolG"]);
  }
  if(s.identityUnclear || s.cat==="X"){
    M("warn","Identitätsfeststellung","Feststellung und Sicherung der Identität; Mitwirkungspflicht; ggf. Festhalten, Durchsuchung, ED-Maßnahmen, Auslesen von Datenträgern (nur unter den Voraussetzungen des § 48 Abs. 3a).",["§ 23 Abs. 3 BPolG","§ 24 BPolG","§ 49 Abs. 2, 3 AufenthG","§ 48 Abs. 3, 3a AufenthG"]);
  }
  if(atBorderEntry && !passOK && !s.asylum) C("warn","Pass beim Grenzübertritt nicht mitgeführt","Ordnungswidrigkeit; Versuch ahndbar.",["§ 98 Abs. 3 Nr. 3 AufenthG","§ 98 Abs. 4 AufenthG","§ 13 Abs. 1 AufenthG"]);

  /* ================= Strafrecht ================= */
  if(!s.asylum){
    if(unlawfulEntry){
      if(atBorderEntry) C("bad","Versuchte unerlaubte Einreise","Bei Zurückweisung an der Grenzübergangsstelle Versuch prüfen.",["§ 95 Abs. 1 Nr. 3 AufenthG","§ 95 Abs. 3 AufenthG"]);
      else C("bad","Unerlaubte Einreise","Einreise ohne erforderlichen Pass oder Aufenthaltstitel.",["§ 95 Abs. 1 Nr. 3 AufenthG","§ 14 Abs. 1 AufenthG"]);
    }
    if(lawful===false && !atBorderEntry && s.title!=="duldung" && s.title!=="gestattung"){
      C("bad","Unerlaubter Aufenthalt","Voraussetzungen: kein Titel, vollziehbar ausreisepflichtig, keine/abgelaufene Ausreisefrist, Abschiebung nicht ausgesetzt. Fahrlässig: OWi.",["§ 95 Abs. 1 Nr. 2 AufenthG","§ 98 Abs. 1 AufenthG"]);
      if(!passOK) C("warn","Aufenthalt ohne Pass","Wenn auch kein Ausweisersatz vorhanden ist.",["§ 95 Abs. 1 Nr. 1 AufenthG","§ 3 Abs. 1 AufenthG","§ 48 Abs. 2 AufenthG"]);
    }
  }
  if(s.smuggling) C("bad","Einschleusen von Ausländern","Fahrer/Begleiter als Beschuldigte; Fahrzeug, Mobiltelefone sicherstellen; geschleuste Personen als Zeugen.",["§ 96 AufenthG","§ 97 AufenthG","§ 94 StPO","§ 98 StPO"]);
  if(R.level==="ok" && R.crim.some(c=>c.lvl==="bad"||c.lvl==="warn")){
    R.level="warn"; R.head="Aufenthalt gedeckt – Verstöße festgestellt"; R.sub=basis+". Aufenthaltsstatus besteht, aber Straf-/Bußgeldtatbestände sind zu prüfen.";
  }

  commonTail(s,R,{M,N,H,P,minor,lawful});
  return R;
}

function commonTail(s,R,{M,N,H,P,minor,lawful}){
  if(minor){
    if(s.age<14) H("Strafunmündig","Kein Strafverfahren gegen das Kind.",["§ 19 StGB"]);
    else H("Jugendlicher","JGG beachten; Erziehungsberechtigte benachrichtigen.",["§ 67 JGG","§ 67a JGG"]);
    if(s.unaccompanied){
      M("bad","Unbegleitete/r Minderjährige/r: Jugendamt","Vorläufige Inobhutnahme durch das Jugendamt veranlassen; Kindeswohl vorrangig; Alterseinschätzung durch Jugendamt. ED-Maßnahmen im Beisein des Jugendamts und kindgerecht.",["§ 42a SGB VIII","§ 42f SGB VIII","§ 71 Abs. 4 AufenthG","Art. 24 GRCh","Art. 3 UN-KRK"]);
      H("Aufenthaltsbeendigung bei Minderjährigen","Abschiebung nur bei Übergabe an Familienangehörige, Personensorgeberechtigte oder geeignete Aufnahmeeinrichtung; Haft grds. nicht.",["§ 58 Abs. 1a AufenthG","§ 62 Abs. 1 AufenthG","Art. 10, 17 2008/115"]);
      P("Unbegleitet minderjährig → Jugendamt (§ 42a SGB VIII).");
    }
  }
  if(R.crim.some(c=>c.lvl==="bad"||c.lvl==="warn"))
    H("Beschuldigtenbelehrung","Belehrung in verständlicher Sprache, Dolmetscher, Recht auf Verteidiger; bei Festnahme schriftliche Belehrung.",["§ 136 StPO","§ 163a Abs. 4 StPO","§ 114b StPO","§ 187 GVG","2012/13"]);
  if(R.meas.some(m=>/haft|Festhalten|Festnahme/i.test(m.t))){
    N("Konsularische Benachrichtigung","Bei Freiheitsentziehung: Belehrung über Recht auf Benachrichtigung der Auslandsvertretung; auf Wunsch unverzüglich benachrichtigen (bei Schutzsuchenden nur mit Zustimmung!).",["Art. 36 WÜK","§ 114b Abs. 2 StPO"]);
    N("Benachrichtigung Angehöriger/Vertrauensperson","Bei Freiheitsentziehung.",["Art. 104 Abs. 4 GG"]);
  }
  if(lawful===false || s.asylum || s.restrictViol) N("Ausländerbehörde / BAMF","Mitteilung über ausländerrechtlich relevante Sachverhalte; AZR-Speicherung.",["§ 87 Abs. 2 AufenthG","§ 2 AZRG"]);
  H("Datenschutz / Dokumentation","Maßnahme und Erwägungen im Vermerk dokumentieren; nur erforderliche Daten erheben.",["§ 29 BPolG","BDSG","2016/680"],true);
}

