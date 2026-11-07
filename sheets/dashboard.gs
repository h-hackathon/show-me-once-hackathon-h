/**
 * Show me once — Google Sheet « Campagnes email — Dashboard hebdo »
 *
 * Installation (5 min) :
 *  1. Crée un Google Sheet vide → Extensions > Apps Script → colle ce fichier → change TOKEN ci-dessous.
 *  2. Sélectionne la fonction `setup` → Exécuter (autorise l'accès). Ça crée les 10 onglets pays + l'onglet Dashboard.
 *  3. Déployer > Nouveau déploiement > type « Application Web » : Exécuter en tant que « Moi », Accès « Tout le monde ».
 *     Copie l'URL /exec dans SHEET_WEBAPP_URL du .env (sert à notre vérificateur, pas à l'agent).
 *  4. Partager le Sheet : « Tous les utilisateurs disposant du lien » → Éditeur. L'agent n'a ainsi jamais à se connecter à Google.
 */
const TOKEN = 'CHANGE-MOI';   // même valeur que SHEET_TOKEN dans .env
const PAYS = ['FR', 'IT', 'ES', 'DE', 'BE', 'PT', 'NL', 'PL', 'GB', 'CH'];
const COLS = ['campagne_id', 'campagne', 'date_envoi', 'envois', 'ouvertures', 'clics',
              'desabonnements', 'commandes', 'ca_eur', 'taux_ouverture', 'taux_clic'];

function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setSpreadsheetLocale('en_US');   // le texte collé depuis Databricks utilise le point décimal
  ss.rename('Campagnes email — Dashboard hebdo');
  const dash = ss.getSheetByName('Dashboard') || ss.insertSheet('Dashboard', 0);
  PAYS.forEach(p => {
    const sh = ss.getSheetByName(p) || ss.insertSheet(p);
    if (sh.getLastRow() === 0) sh.getRange(1, 1, 1, COLS.length).setValues([COLS]);
    sh.getRange(1, 1, 1, COLS.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  });
  ['Sheet1', 'Feuille 1', 'Feuille1'].forEach(n => {
    const s = ss.getSheetByName(n);
    if (s && ss.getSheets().length > 1) ss.deleteSheet(s);
  });
  buildDashboard_(dash);
}

function buildDashboard_(dash) {
  dash.clear();
  dash.getCharts().forEach(c => dash.removeChart(c));
  dash.getRange('A1').setValue('Campagnes email — rapport hebdo par pays').setFontSize(16).setFontWeight('bold');
  dash.getRange('A2').setValue('Dernière mise à jour d\'un onglet :');
  const head = ['Pays', 'Campagnes', 'Envois', 'Ouvertures', 'Clics', 'Commandes', 'CA (€)', 'Taux ouverture (%)', 'Taux clic (%)'];
  dash.getRange(4, 1, 1, head.length).setValues([head]).setFontWeight('bold').setBackground('#0082C3').setFontColor('white');
  const rows = PAYS.map((p, i) => {
    const r = 5 + i;
    return [p, `=COUNTA('${p}'!A2:A)`, `=SUM('${p}'!D2:D)`, `=SUM('${p}'!E2:E)`, `=SUM('${p}'!F2:F)`,
            `=SUM('${p}'!H2:H)`, `=SUM('${p}'!I2:I)`,
            `=IFERROR(ROUND(100*D${r}/C${r},1),0)`, `=IFERROR(ROUND(100*E${r}/C${r},1),0)`];
  });
  dash.getRange(5, 1, rows.length, head.length).setValues(rows);
  const t = 5 + PAYS.length;
  dash.getRange(t, 1, 1, head.length).setValues([['Total', `=SUM(B5:B${t - 1})`, `=SUM(C5:C${t - 1})`, `=SUM(D5:D${t - 1})`,
    `=SUM(E5:E${t - 1})`, `=SUM(F5:F${t - 1})`, `=SUM(G5:G${t - 1})`,
    `=IFERROR(ROUND(100*D${t}/C${t},1),0)`, `=IFERROR(ROUND(100*E${t}/C${t},1),0)`]]).setFontWeight('bold');
  dash.getRange(5, 7, PAYS.length + 1, 1).setNumberFormat('#,##0.00 €');

  const chart = (col, title, row) => dash.insertChart(dash.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(dash.getRange(`A4:A${t - 1}`)).addRange(dash.getRange(`${col}4:${col}${t - 1}`))
    .setNumHeaders(1).setPosition(row, 11, 0, 0)
    .setOption('title', title).setOption('legend', { position: 'none' }).setOption('colors', ['#0082C3'])
    .setOption('width', 560).setOption('height', 300).build());
  chart('G', 'Chiffre d\'affaires attribué par pays (€)', 1);
  chart('H', 'Taux d\'ouverture par pays (%)', 17);
  dash.autoResizeColumns(1, head.length);
}

/** Horodatage visible en démo : « mis à jour il y a 3 s ». */
function onEdit(e) {
  const sh = e && e.range && e.range.getSheet();
  if (sh && PAYS.indexOf(sh.getName()) >= 0) {
    sh.getParent().getSheetByName('Dashboard').getRange('C2').setValue(`${sh.getName()} — ${new Date().toLocaleString('fr-FR')}`);
  }
}

// ---------- mini API pour notre vérificateur (lecture + remise à zéro) ----------
function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  if ((e.parameter.token || '') !== TOKEN) return json_({ error: 'token' });
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const tz = ss.getSpreadsheetTimeZone();
  const tabs = {};
  PAYS.forEach(p => {
    const sh = ss.getSheetByName(p);
    tabs[p] = sh ? sh.getDataRange().getValues().map(r => r.map(c =>
      c instanceof Date ? Utilities.formatDate(c, tz, 'yyyy-MM-dd') : c)) : null;
  });
  return json_({ tabs: tabs, dashboard: ss.getSheetByName('Dashboard') ? true : false });
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents || '{}');
  if (body.token !== TOKEN) return json_({ error: 'token' });
  if (body.action !== 'reset') return json_({ error: 'action' });
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  Object.keys(body.tabs || {}).forEach(p => {
    const sh = ss.getSheetByName(p) || ss.insertSheet(p);
    sh.clearContents();
    const values = [COLS].concat(body.tabs[p]);
    sh.getRange(1, 1, values.length, COLS.length).setValues(values);
    sh.getRange(1, 1, 1, COLS.length).setFontWeight('bold');
  });
  const d = ss.getSheetByName('Dashboard');
  if (d) d.getRange('C2').setValue('remis à zéro (semaine précédente)');
  return json_({ ok: true, tabs: Object.keys(body.tabs || {}).length });
}
