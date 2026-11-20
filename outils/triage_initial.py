"""Triage initial (à la main, d'après les vignettes) : zone supposée de chaque photo."""
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
Z = {
 **{f"P{i:02d}": ("int-bibliotheque", "Bibliothèque boisée : piano, canapé, tapis persan, plafond à caissons blancs") for i in range(0, 4)},
 **{f"P{i:02d}": ("int-palier-etage", "Palier de l'étage : coupole à lanterneau, tapisserie, rampe fer forgé, portes cintrées") for i in range(4, 14)},
 **{f"P{i:02d}": ("int-escalier", "Escalier d'honneur : marbre, tapis rouge, main courante laiton") for i in range(14, 20)},
 "P20": ("int-vestibule", "Depuis l'escalier vers le vestibule : colonnes, rideaux rouges"),
 "P21": ("int-vestibule", "Vestibule : colonnes, tapis rouge, lustre"),
 **{f"P{i:02d}": ("int-couloir-rdc", "Couloir RDC : papier peint damassé, sol marbre à cabochons, fusil") for i in range(22, 25)},
 "P25": ("int-petit-salon", "Petit salon/antichambre damassé, guéridon, fauteuils rouges"),
 "P26": ("int-petit-salon", "Petit salon : desserte, banquette rouge"),
 **{f"P{i:02d}": ("int-salon-bow-window", "Salon à bow-window (avant-corps jardin), parquet, lustre") for i in range(27, 30)},
 "P30": ("int-salon-tableau", "Pièce au grand tableau marine, commode, vers billard"),
 "P31": ("int-salon-tableau", "Grand tableau marine, enfilade vers le billard"),
 **{f"P{i:02d}": ("int-billard", "Salle de billard : plafond à caissons peints, cheminée bois, tapis") for i in range(32, 36)},
 "P36": ("int-couloir-rdc", "Couloir vers billard, fenêtres sur balconnet"),
 **{f"P{i:02d}": ("ext-facade-nord", "Façade d'entrée (nord) : perron, porte bois sculptée, lampadaires") for i in range(37, 41)},
 "P41": ("int-vestibule", "Vestibule d'entrée axe escalier : tapis, table dorée, colonnes"),
 "P42": ("int-couloir-rdc", "Couloir le long de l'escalier, console miroir"),
 **{f"P{i:02d}": ("int-salle-a-manger", "Salle à manger : lambris vert/jaune, longue table, buffets") for i in range(43, 47)},
 **{f"P{i:02d}": ("int-chambre-1", "Chambre : lit, tapis, armoire, 2 fenêtres") for i in range(47, 50)},
 **{f"P{i:02d}": ("int-bureau", "Bureau : cheminée marbre blanc, grande table, lambris") for i in range(50, 52)},
 **{f"P{i:02d}": ("int-chambre-2", "Chambre à rayures : cheminée, jouets") for i in range(52, 55)},
 **{f"P{i:02d}": ("int-chambre-3", "Pièce à l'armoire et tableau marine") for i in range(55, 58)},
 "W01": ("ext-facade-sud", "Façade jardin (sud) frontale : perron, balcon central, balustrade terrasse"),
 "W02": ("ext-facade-est", "Angle 3/4, olivier, terrasse balustrée"),
 "W03": ("ext-jardin", "Vue aérienne du parc : pelouse, bassin en haricot, mât, allée"),
 "W04": ("ext-toiture", "Toiture : tuiles canal, souches de cheminée, verrière, balustrades ; vue mer"),
 "W05": ("ext-jardin", "Aérien face jardin : bassin, mâts, pelouse, perron"),
 "W06": ("ext-facade-nord", "Plaque « Château Saint-Victor », chapiteaux, porte et imposte fer forgé"),
 "W07": ("int-salon-vert", "Salon vert à pan coupé : cheminée marbre rose, trumeau doré, pendule"),
 "W08": ("int-vestibule", "Vestibule : rideaux rouges, porte-manteau, escalier fer forgé"),
 "W09": ("int-escalier", "Cage d'escalier vue de dessus : forme, marbre à cabochons"),
 "W10": ("ext-toiture", "Toiture côté jardin : verrière, 9 souches, croupes"),
 "W11": ("ext-facade-nord", "Aérien façade nord : entrée, parking, tennis"),
 "W12": ("ext-emprise", "Vue zénithale : emprise exacte, toitures, terrasses, tennis, parking"),
 "W13": ("ext-facade-sud", "Façade jardin rapprochée : ferronneries, parasols"),
 "W14": ("int-salon-vert", "Détail pendule cavalier et candélabres"),
 "W15": ("ext-facade-sud", "Aérien façade jardin + terrasse, tennis, piscine"),
 "W16": ("ext-jardin", "Aérien large : platanes, cour sablée, palmiers"),
 "W17": ("ext-facade-est", "Façade latérale : volets persiennés, lanternes"),
 "W18": ("ext-jardin", "Aérien très large du parc"),
}
brut = json.loads((R / "travail/photos-brut.json").read_text())
for p in brut:
    p["zone"], p["note"] = Z.get(p["id"], ("a-classer", ""))
    p["statut"] = "triee"
(R / "travail/photos.json").write_text(json.dumps(brut, ensure_ascii=False, indent=1))
print(len(brut), "photos triées")
