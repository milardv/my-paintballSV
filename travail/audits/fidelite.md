# Vérification des sources et du décor — 15 novembre 2026

Les scripts utilisent les photographies comme références de forme, disposition, couleurs et sujets. Les quatre scripts intérieurs ne chargent pas les clichés Pixel comme textures : les tapis, papiers peints, marbres et tableaux sont majoritairement procéduraux ; les bois et certains assets proviennent des matériaux génériques documentés dans assets/LICENCES.md. Par exemple, piece_chambres.py indique explicitement que ses tableaux sont peints procéduralement, sans copie de photo.

L’inventaire contient 757 éléments dédupliqués. Les GLB des pièces contiennent 75, 109, 143 et 273 nœuds, mais ces nombres ne mesurent pas la couverture : certains objets regroupent de nombreuses géométries et d’autres sont des instances. Il n’existe pas de correspondance élément inventorié → objet GLB permettant de certifier l’exhaustivité. Le mobilier majeur, les moulures, cheminées, tapis et accessoires sont présents ; la fidélité détaillée de chaque objet reste à comparer aux photos.

Le bassin est présent dans parc.py et parc.glb : forme en haricot, centre Blender D-003 (8 ; 85), margelle, fond, surface d’eau, trois jets, presqu’île et mâts. Le gabarit initial situait un bassin estimé en (5 ; 75) ; le modèle détaillé emploie la position ci-dessus. La position et les dimensions sont estimées depuis les références web, pas mesurées sur place.

Les photographies restent des références hors application, conformément à la demande de Valentin. Aucune galerie photo ni texture issue d’un cliché n’est ajoutée à l’interface.
