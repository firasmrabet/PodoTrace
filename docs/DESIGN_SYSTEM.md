# DiaFoot Sentinel — Design System « Sérénité »

> **Principe directeur** : la lisibilité clinique avant l'effet. Une seule
> couleur saturée est interdite à l'écran ; aucun halo, aucun clignotement,
> aucune animation nerveuse. L'interface doit pouvoir être regardée pendant une
> consultation de 20 minutes sans fatiguer l'œil, tout en restant habitée
> (typo serif, matière papier, micro-mouvements amples).

Ce document est la **source de vérité** du système. Il est implémenté deux fois,
avec les mêmes valeurs :

| Cible | Fichier | Statut |
|---|---|---|
| Interface web (servie par FastAPI) | `web/css/app.css` | ✅ actif, c'est l'interface de référence |
| Application Flutter (mobile / web) | `app_flutter/lib/core/theme/df_theme.dart` | ✅ aligné (palette + typo + thème clair) |

> ℹ️ L'ancienne direction artistique « Bio-Luxe » (prune/cuivre, aurores,
> grain animé, serif de luxe) a été **abandonnée** et retirée du dépôt. Ne pas
> la réintroduire : ni `#10070D`, ni `#C9924E`, ni dégradés radiaux colorés.

---

## 1. Couleurs

### Papiers (fonds)

| Token | Valeur | Usage |
|---|---|---|
| `--paper` | `#F4F2EC` | fond général de l'application (chaud, non blanc : moins d'éblouissement) |
| `--paper-2` | `#EFEBE2` | zones en retrait (rails, pieds de page) |
| `--surface` | `#FFFFFF` | cartes, feuilles, champs |
| `--surface-soft` | `#FAF8F3` | survol de carte, en-têtes de tableau |
| `--surface-sink` | `#F2EFE7` | puces, badges neutres, pistes de graphique |

### Encres (textes)

| Token | Valeur | Contraste mesuré | Usage |
|---|---|---|---|
| `--ink` | `#16302B` | **12,6:1** sur `--paper` | titres, valeurs, texte principal |
| `--ink-2` | `#3D5650` | **7,1:1** | texte courant secondaire |
| `--ink-3` | `#5E736B` | **4,53:1** | légendes, métadonnées (seuil AA respecté) |
| `--muted` | `#8B9A95` | 2,6:1 | **décoratif uniquement** (filets, libellés d'axe) — jamais du texte porteur de sens |
| `--line` | `#E4E0D6` | — | bordures de cartes et de champs |
| `--line-soft` | `#EDEAE2` | — | séparateurs internes |

### Végétal (accent unique)

| Token | Valeur | Usage |
|---|---|---|
| `--sage` | `#5C8570` | traits, icônes actives, focus, points de graphique |
| `--sage-deep` | `#3F6152` | **fonds de boutons primaires** (blanc dessus = 6,7:1), liens |
| `--sage-tint` | `#E7EFE9` | fond d'état sélectionné |
| `--sand` / `--sand-tint` | `#E8DCC6` / `#F5EEE0` | matière secondaire, entêtes de section |

### Signaux cliniques

Chaque signal existe en **couleur + teinte de fond**, et **jamais seul** : il est
toujours doublé d'un mot (« Élevé », « À valider ») et d'une icône.

| Signal | Couleur | Teinte | Sens |
|---|---|---|---|
| `--calm` | `#5C8570` | `#E9F0EB` | favorable, cicatrisation, risque faible |
| `--watch` | `#B98C3C` | `#F7EFDE` | à surveiller, risque modéré |
| `--alert` | `#A9535C` | `#F6E8E9` | risque élevé, drapeau rouge, urgence |
| `--info` | `#6F93B0` | `#EAF0F5` | information, incertitude du modèle |

> ⚠️ `--watch` et `--info` ont un contraste < 4,5:1 sur `--paper` : ils servent
> de **fond** ou de **puce**, jamais de couleur de texte seule. Le texte d'un
> badge « à surveiller » est `--ink` sur `--watch-tint`.

### Tissus (aligné sur le backend)

| Token | Valeur | Tissu |
|---|---|---|
| `--t-necrosis` | `#4E4044` | nécrose |
| `--t-fibrin` | `#DCC48A` | fibrine |
| `--t-granulation` | `#B56A57` | granulation |
| `--t-epithelial` | `#E7B5A8` | épithélialisation |

Le même mapping est utilisé par la légende du donut, la segmentation colorisée et
le rapport PDF — une couleur de tissu ne change **jamais** d'un écran à l'autre.

---

## 2. Typographie

| Rôle | Police | Taille | Détail |
|---|---|---|---|
| Titre d'écran `h1` | serif (`Iowan Old Style`, Palatino, Georgia) | `clamp(26px, 3.4vw, 38px)`, 1.12 | poids 600, `letter-spacing -.012em` |
| Titre de section `h2` | idem | 22px / 1.2 | |
| Sous-titre `h3` | idem | 17px / 1.25 | |
| Texte courant | `Inter`, system-ui | 14px / 1.6 | `--ink-2` sur carte |
| Donnée compacte `.small` | Inter | 12px | `--ink-3` |
| Surtitre `.eyebrow` | Inter | 10px, `letter-spacing .19em`, majuscules | `--muted` |
| Chiffre-clé (tuile) | serif | 25–30px | chiffres tabulaires via `--mono` pour les tables |

Règles : **une seule famille serif** pour les titres, jamais en dessous de 22px ;
Inter pour tout ce qui se lit vite ; aucune lettre capitale sur plus de 4 mots.

---

## 3. Géométrie & matière

| Token | Valeur | Usage |
|---|---|---|
| `--r-xl` | 22px | feuilles, cartes principales |
| `--r-lg` | 16px | cartes internes, modales |
| `--r-md` | 11px | champs, boutons secondaires |
| `--r-sm` | 8px | puces, badges, onglets |
| `--sh-1` | `0 1px 2px rgba(22,48,43,.05), 0 10px 24px -20px rgba(22,48,43,.30)` | carte au repos |
| `--sh-2` | `0 1px 2px rgba(22,48,43,.05), 0 20px 44px -30px rgba(22,48,43,.34)` | carte survolée, feuille |
| `--sh-in` | `inset 0 1px 0 rgba(255,255,255,.7)` | liseré lumineux supérieur |

Ombres **très** diffuses, teintées d'encre verte (jamais du noir pur) : elles
posent la carte sans créer de halo. Grain de papier `2,5 %` en `body::before`,
fixe, invisible à la lecture — c'est la seule texture autorisée.

Grille : rail latéral `238px` + contenu `1040px` centré ; passage en barre
d'onglets inférieure à `≤ 900px`.

---

## 4. Composants

| Composant | Classe | Règles |
|---|---|---|
| Carte | `.card` | fond `--surface`, `--r-xl`, `--sh-1`, padding 18–24px, jamais deux cartes collées sans 14px |
| Tuile de mesure | `.tile` | surtitre 10px + valeur serif + pied explicatif ; la valeur porte l'unité en petit |
| Bouton primaire | `.btn` | fond `--sage-deep`, texte `#FBFCFA`, 13px/600, `--r-md`, ombre 1px |
| Bouton fantôme | `.btn.ghost` | bordure `--line`, texte `--ink` |
| Action discrète | `.btn.quiet` | texte `--sage-deep`, pas de fond avant survol |
| Badge d'état | `.pill` | teinte + texte encre + point 6px ; jamais plus de 2 par ligne |
| Bandeau | `.banner` | icône 34px + titre + phrase ; `calm`/`watch`/`alert`/`info` |
| Champ | `.input` | `--surface`, bordure `--line`, focus = bordure `--sage` + halo `rgba(92,133,112,.13)` |
| Bascule | `.seg` | 2–3 options, actif = `--sage-tint` + texte `--sage-deep` |
| Ligne de plaie | `.wound-row` | pastille 40px + nom + méta + valeur + badge + lien ; `≤ 900px` : retour à la ligne, sparkline masquée |
| Tableau de suivi | `.table` | entêtes 10px majuscules `--muted`, lignes séparées par `--line-soft`, chiffres tabulaires |
| Barre de progression (risque) | `.meter` | piste `--surface-sink`, remplissage dégradé doux du signal, pas d'animation |
| Toasts | `.toast` | bas-droite, `--sage-deep` (succès) / `--alert` (erreur), 3,2 s |

### États obligatoires
`hover` (+2 % de luminosité max), `active` (translation 1px), `focus-visible`
(anneau `--sage` 2px), `disabled` (opacité .45, curseur par défaut),
`loading` (spinner 1px `--sage-deep`, jamais de squelette clignotant).

---

## 5. Mouvement

| Token | Valeur | Usage |
|---|---|---|
| `--ease` | `cubic-bezier(.22,.61,.36,1)` | tout |
| `--t-fast` | 170 ms | survols, focus, bascules |
| `--t-mid` | 280 ms | apparition de carte, toast |
| `--t-slow` | 460 ms | transition d'écran (fondu + 6px de montée) |

Règles : **une seule** propriété animée par transition, amplitude ≤ 8px,
aucune boucle infinie sauf le spinner (1,1 s) et la pulsation du point
« enregistrement ». `@media (prefers-reduced-motion: reduce)` ramène toute
animation à 0,001 ms — implémenté globalement.

---

## 6. Iconographie

Tracés 1,6px, `stroke-linecap:round`, 16/17/20px, jeu maison dans
`web/js/core.js` (`icon()`), aucun emoji dans l'interface, aucune bibliothèque
externe (l'application doit fonctionner hors-ligne, sans CDN).

---

## 7. Accessibilité

- Cibles tactiles ≥ 44px sur mobile ; zone de clic des liens de ligne = toute la ligne.
- Contraste : tout texte porteur de sens ≥ 4,5:1 (voir tableaux §1).
- Chaque signal couleur est doublé d'un libellé et d'une icône (jamais la couleur seule).
- `alt` explicites sur les couches d'image (segmentation, Grad-CAM décrits en toutes lettres).
- Navigation clavier complète, ordre DOM linéaire, `aria-live="polite"` sur la réponse de l'assistant.
- Textes en français, tailles relatives (`rem` pour le Flutter, `px` clampés pour le web).

---

## 8. Interdits (décisions arrêtées)

1. Pas de dégradé saturé, pas de glassmorphism coloré, pas d'aurore, pas de glow.
2. Pas de noir pur ni de blanc pur en fond plein écran.
3. Pas de typo décorative en dessous de 22px, pas de capitales espacées sur du texte long.
4. Pas d'animation au défilement, pas de parallaxe, pas de compteur qui s'incrémente.
5. Pas de couleur de tissu ou de risque réutilisée à des fins décoratives.
6. Pas d'emoji, pas d'illustration « cartoon » : uniquement des tracés et des photos cliniques.
