/**
 * Show me once — Google Sheet « Campagnes email — Dashboard hebdo »
 * (fichier généré par `python -m som notebooks` : ne pas modifier sheets/dashboard.gs à la main)
 *
 * Installation (3 min) :
 *  1. Crée un Google Sheet vide → Extensions > Apps Script → colle ce fichier → Cmd + S.
 *  2. Choisis la fonction `setup` → Exécuter (autorise l'accès).
 *     Ça crée les 10 onglets pays (remplis avec la semaine précédente) + l'onglet Dashboard et ses graphiques.
 *  3. Partager le Sheet : « Tous les utilisateurs disposant du lien » → Éditeur. L'agent n'a jamais à se connecter à Google.
 *
 * Avant chaque lot du benchmark : menu « Show me once » → « Remettre à zéro ».
 * L'agent, lui, n'utilise pas ce script : il colle les données directement dans les onglets, comme un humain.
 */
const PAYS = ['FR', 'IT', 'ES', 'DE', 'BE', 'PT', 'NL', 'PL', 'GB', 'CH'];
const COLS = ['campagne_id', 'campagne', 'date_envoi', 'envois', 'ouvertures', 'clics',
              'desabonnements', 'commandes', 'ca_eur', 'taux_ouverture', 'taux_clic'];
// État « avant » : rapport de la semaine précédente (même calcul que la vérité terrain du repo)
const PRECEDENTE = {"FR": [["CMP-FR-013", "Tennis — Petits prix", "2026-10-20", 676, 190, 16, 0, 4, 518.02, 28.1, 2.4], ["CMP-FR-014", "Ski — Conseils d'expert", "2026-10-22", 695, 212, 28, 1, 3, 442.16, 30.5, 4.0]], "IT": [["CMP-IT-013", "Yoga — Petits prix", "2026-10-20", 641, 167, 22, 1, 2, 145.26, 26.1, 3.4], ["CMP-IT-014", "Camping — Spécial week-end", "2026-10-22", 443, 151, 26, 0, 4, 276.8, 34.1, 5.9]], "ES": [["CMP-ES-013", "Vélo — Essentiels de saison", "2026-10-20", 472, 132, 13, 0, 2, 38.39, 28.0, 2.8], ["CMP-ES-014", "Tennis — Conseils d'expert", "2026-10-22", 526, 225, 28, 2, 4, 497.87, 42.8, 5.3]], "DE": [["CMP-DE-013", "Fitness — Conseils d'expert", "2026-10-20", 535, 209, 27, 0, 2, 369.71, 39.1, 5.0], ["CMP-DE-014", "Vélo — Nouveautés", "2026-10-22", 538, 223, 31, 0, 3, 407.85, 41.4, 5.8]], "BE": [["CMP-BE-013", "Fitness — Conseils d'expert", "2026-10-20", 612, 242, 41, 1, 4, 566.77, 39.5, 6.7], ["CMP-BE-014", "Running — Conseils d'expert", "2026-10-22", 440, 192, 19, 0, 2, 249.43, 43.6, 4.3]], "PT": [["CMP-PT-013", "Tennis — Petits prix", "2026-10-20", 546, 220, 25, 3, 3, 207.02, 40.3, 4.6], ["CMP-PT-014", "Running — Conseils d'expert", "2026-10-22", 565, 176, 25, 0, 3, 383.67, 31.2, 4.4]], "NL": [["CMP-NL-013", "Vélo — Spécial week-end", "2026-10-20", 516, 172, 22, 1, 3, 353.27, 33.3, 4.3], ["CMP-NL-014", "Fitness — Petits prix", "2026-10-22", 617, 261, 34, 1, 7, 722.49, 42.3, 5.5]], "PL": [["CMP-PL-013", "Natation — Petits prix", "2026-10-20", 576, 127, 21, 0, 5, 994.98, 22.0, 3.6], ["CMP-PL-014", "Natation — Conseils d'expert", "2026-10-22", 521, 177, 17, 0, 1, 119.0, 34.0, 3.3]], "GB": [["CMP-GB-013", "Fitness — Petits prix", "2026-10-20", 661, 265, 36, 1, 4, 662.69, 40.1, 5.4], ["CMP-GB-014", "Yoga — Conseils d'expert", "2026-10-22", 776, 255, 31, 2, 2, 387.07, 32.9, 4.0]], "CH": [["CMP-CH-013", "Tennis — Essentiels de saison", "2026-10-20", 435, 135, 16, 0, 1, 185.2, 31.0, 3.7], ["CMP-CH-014", "Running — Conseils d'expert", "2026-10-22", 342, 150, 15, 0, 3, 366.99, 43.9, 4.4]]};

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Show me once')
    .addItem('Remettre à zéro (semaine précédente)', 'remettreAZero')
    .addItem('Reconstruire le Dashboard', 'setup')
    .addToUi();
}

function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setSpreadsheetLocale('en_US');   // le texte collé depuis Databricks utilise le point décimal
  ss.rename('Campagnes email — Dashboard hebdo');
  const dash = ss.getSheetByName('Dashboard') || ss.insertSheet('Dashboard', 0);
  PAYS.forEach(p => { if (!ss.getSheetByName(p)) ss.insertSheet(p); });
  ['Sheet1', 'Feuille 1', 'Feuille1'].forEach(n => {
    const s = ss.getSheetByName(n);
    if (s && ss.getSheets().length > 1) ss.deleteSheet(s);
  });
  remettreAZero();
  buildDashboard_(dash);
}

function remettreAZero() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  PAYS.forEach(p => {
    const sh = ss.getSheetByName(p) || ss.insertSheet(p);
    sh.clearContents();
    const values = [COLS].concat(PRECEDENTE[p] || []);
    sh.getRange(1, 1, values.length, COLS.length).setValues(values);
    sh.getRange(1, 1, 1, COLS.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  });
  const d = ss.getSheetByName('Dashboard');
  if (d) d.getRange('C2').setValue('remis à zéro (semaine précédente)');
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

/** Horodatage visible en démo : « FR — 08/11/2026 10:42 ». */
function onEdit(e) {
  const sh = e && e.range && e.range.getSheet();
  if (sh && PAYS.indexOf(sh.getName()) >= 0) {
    sh.getParent().getSheetByName('Dashboard').getRange('C2').setValue(`${sh.getName()} — ${new Date().toLocaleString('fr-FR')}`);
  }
}
