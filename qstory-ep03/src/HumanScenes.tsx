import React from 'react';

type HumanSceneProps = {t: number};

const clamp = (n: number) => Math.max(0, Math.min(1, n));
const smooth = (n: number) => {
  const x = clamp(n);
  return x * x * (3 - 2 * x);
};
const window = (t: number, start: number, end: number, feather = 1.5) =>
  smooth((t - start) / feather) * (1 - smooth((t - end) / feather));
const pulse = (t: number, speed: number, phase = 0) => 0.5 + 0.5 * Math.sin(t * speed + phase);

const Desk = ({t, returning = false}: {t: number; returning?: boolean}) => {
  const breath = 0.5 + pulse(t, 0.72, 1.4) * 0.5;
  const penNudge = returning ? (t - 165) * 0.9 : Math.sin(t * 0.72) * 2.2;
  return <g>
    <defs>
      <linearGradient id="human-desk-wood" x1="0" y1="0" x2="1" y2="1">
        <stop stopColor="#30241d"/><stop offset=".48" stopColor="#191b1a"/><stop offset="1" stopColor="#111719"/>
      </linearGradient>
      <linearGradient id="human-paper" x1="0" y1="0" x2=".8" y2="1">
        <stop stopColor="#dfcfaa"/><stop offset=".58" stopColor="#baaa86"/><stop offset="1" stopColor="#897d65"/>
      </linearGradient>
      <linearGradient id="human-hand" x1="0" y1="0" x2=".9" y2="1">
        <stop stopColor="#d8a875"/><stop offset=".55" stopColor="#aa7954"/><stop offset="1" stopColor="#664a39"/>
      </linearGradient>
      <radialGradient id="human-lamp-pool">
        <stop stopColor="#f1bb70" stopOpacity=".23"/><stop offset=".58" stopColor="#ca8b4d" stopOpacity=".09"/><stop offset="1" stopColor="#b36d3d" stopOpacity="0"/>
      </radialGradient>
      <linearGradient id="human-soundline" x1="0" y1="0" x2="1" y2="0">
        <stop stopColor="#f0c887" stopOpacity="0"/><stop offset=".2" stopColor="#efc982" stopOpacity=".18"/><stop offset=".72" stopColor="#fff0cc" stopOpacity=".9"/><stop offset="1" stopColor="#c7e7eb" stopOpacity=".12"/>
      </linearGradient>
    </defs>

    <ellipse cx="960" cy="500" rx="900" ry="470" fill="url(#human-lamp-pool)" opacity={.78 + breath * .12}/>
    <path d="M110 591 Q430 552 764 580 Q1260 613 1810 564 L1810 850 L110 850Z" fill="url(#human-desk-wood)"/>
    <path d="M110 610 Q560 571 950 608 T1810 580" fill="none" stroke="#c28d58" strokeOpacity=".21" strokeWidth="2"/>
    <path d="M150 734 Q508 702 820 737 M1238 696 Q1507 676 1790 702 M225 801 Q475 784 689 803" fill="none" stroke="#c09364" strokeOpacity=".11" strokeWidth="2"/>
    <path d="M477 150 L477 211" stroke="#3d3b34" strokeWidth="4"/>
    <path d="M417 211 Q431 189 476 187 Q523 191 539 217 L522 236 L433 237Z" fill="#242826" stroke="#8b765b" strokeOpacity=".58" strokeWidth="2"/>
    <path d="M437 228 Q476 240 519 226" fill="none" stroke="#f0bd79" strokeOpacity={.42 + breath * .16} strokeWidth="3"/>
    <ellipse cx="775" cy="395" rx="520" ry="330" fill="url(#human-lamp-pool)" opacity=".78"/>
    <path d="M281 275 Q720 230 1203 278 L1371 648 Q813 688 394 645Z" fill="#060a0b" opacity=".25" transform="translate(8 13)"/>
    <path d="M269 258 Q712 220 1193 265 L1358 626 Q822 665 379 629Z" fill="url(#human-paper)" stroke="#eedbb0" strokeOpacity=".54" strokeWidth="2"/>
    <path d="M310 290 Q709 259 1155 294 M343 584 Q810 620 1311 587" fill="none" stroke="#665c4c" strokeOpacity=".2" strokeWidth="1.5"/>
    <g transform="rotate(-5 850 446)" fill="none" stroke="#4d4a41" strokeLinecap="round" strokeLinejoin="round">
      <path d="M629 410 C651 337 733 299 811 313 C883 326 927 379 923 433" strokeWidth="3.2" opacity=".72"/>
      <path d="M927 448 C916 518 860 560 787 560 C707 561 649 524 629 467" strokeWidth="2.4" opacity=".65"/>
      <path d="M636 408 Q625 431 630 451 M820 319 Q868 327 894 353" strokeWidth="1.2" opacity=".46"/>
      <path d="M694 455 Q735 417 774 451 L828 420 L858 458" strokeWidth="2" opacity=".62"/>
      <path d="M702 480 L718 529 M742 463 L759 533 M790 455 L799 529 M836 466 L826 518" strokeWidth="1.4" opacity=".48"/>
      <circle cx="870" cy="388" r="27" strokeWidth="1.5" opacity=".42"/>
      <path d="M844 388 H896 M870 362 V414 M949 380 L991 380 M949 396 L1004 396 M948 412 L982 412" strokeWidth="1.3" opacity=".44"/>
      <path d="M470 360 Q514 341 557 359 M483 371 Q524 352 562 370 M1026 510 Q1060 490 1097 506 M1024 520 Q1063 502 1108 518" strokeWidth="1.5" opacity=".38"/>
    </g>
    <text x="1000" y="362" fill="#45453e" fontFamily="serif" fontSize="18" opacity=".66" transform="rotate(-5 1000 362)">dS / dt = ?</text>
    <text x="490" y="537" fill="#4c493f" fontFamily="serif" fontSize="17" opacity=".58" transform="rotate(-5 490 537)">assumption 01</text>

    {/* The sketch's missing stroke stays visible in the first act and returns in the last. */}
    <path d="M740 373 A94 94 0 1 1 741 516" fill="none" stroke="#f0c784" strokeOpacity={.3 + breath * .12} strokeWidth="2" strokeDasharray="4 8"/>

    <path d="M110 663 Q176 632 250 638 L322 619 Q347 612 359 628 L352 655 Q335 682 309 702 L248 729 Q192 742 110 739Z" fill="url(#human-hand)" stroke="#e4b884" strokeOpacity=".38" strokeWidth="2"/>
    <path d="M253 645 Q286 629 327 629 Q346 630 344 645 Q340 656 320 662 L285 678 M277 681 Q315 660 342 656" fill="none" stroke="#4e392d" strokeOpacity=".56" strokeWidth="4" strokeLinecap="round"/>
    <path d="M305 629 Q320 623 336 626" fill="none" stroke="#f0c89b" strokeOpacity=".56" strokeWidth="2" strokeLinecap="round"/>

    <g transform={`rotate(${penNudge * .08} 1030 498)`}>
      <path d="M1028 477 L1183 588" stroke="#191b1a" strokeWidth="17" strokeLinecap="round"/>
      <path d="M1031 473 L1179 580" stroke="#d1b17a" strokeWidth="7" strokeLinecap="round"/>
      <path d="M1178 578 L1199 602 L1170 590Z" fill="#c6ae86"/>
      <path d="M1050 490 L1076 509" stroke="#f3dba8" strokeOpacity=".7" strokeWidth="2"/>
    </g>
    <path d="M1125 639 Q1154 616 1177 603 Q1197 593 1208 602 Q1216 612 1202 625 L1176 647 Q1188 642 1201 647 Q1211 652 1204 663 Q1196 675 1179 677 Q1191 681 1186 692 Q1178 705 1157 705 L1108 704 Q1088 704 1071 688 L1048 665 Q1040 653 1052 642 Q1065 632 1082 641 L1102 652Z" fill="url(#human-hand)" stroke="#e5b581" strokeOpacity=".4" strokeWidth="2"/>
    <path d="M1148 642 Q1162 630 1184 619 M1125 658 Q1150 643 1171 644 M1112 676 Q1140 665 1164 669" fill="none" stroke="#513b2d" strokeOpacity=".53" strokeWidth="3" strokeLinecap="round"/>
    <path d="M104 750 Q322 765 496 748 M1404 741 Q1600 752 1798 725" fill="none" stroke="#d0965e" strokeOpacity=".14" strokeWidth="2"/>

    {returning ? <g opacity={smooth((t - 167.2) / 1.2)}>
      <path d="M622 360 C662 330 718 326 764 342" fill="none" stroke="#ac5944" strokeWidth="3" strokeOpacity=".8" strokeDasharray="2 5"/>
      <path d="M617 356 Q706 306 796 347" fill="none" stroke="#b75c43" strokeWidth="1.4" strokeOpacity=".6"/>
      <circle cx="729" cy="343" r="4" fill="#bf7553" opacity=".8"/>
      <path d="M1207 603 Q1218 594 1225 600" fill="none" stroke="#efc287" strokeWidth="2" strokeOpacity=".65"/>
    </g> : null}
  </g>;
};

const SoundPrelude = ({t}: {t: number}) => {
  const mix = window(t, 6, 11.8, 1.1);
  const shrink = smooth((t - 9.2) / 2.4);
  const cx = 1457 - shrink * 102;
  const cy = 371 - shrink * 32;
  return <g opacity={mix}>
    <path d="M270 370 C330 370 347 346 376 370 S421 394 447 370 S492 344 519 370 S567 395 594 370 S635 346 663 370 S704 393 733 370 S776 346 803 370 S846 393 874 370 S918 344 946 370 S987 396 1015 370 S1057 345 1084 370 S1127 395 1155 370 S1198 344 1225 370 S1269 393 1298 370 S1341 347 1370 370 S1411 392 1444 370" fill="none" stroke="url(#human-soundline)" strokeWidth="4" opacity=".92"/>
    <path d="M270 370 H1447" stroke="#e7c88f" strokeOpacity=".16" strokeWidth="1"/>
    <ellipse cx={cx} cy={cy} rx={198 - shrink * 152} ry={130 - shrink * 98} fill="none" stroke="#c4e4e8" strokeOpacity={.1 + (1 - shrink) * .15} strokeWidth="1.4"/>
    <ellipse cx={cx} cy={cy} rx={137 - shrink * 108} ry={88 - shrink * 67} fill="none" stroke="#e4c986" strokeOpacity={.17} strokeWidth="1" transform={`rotate(-18 ${cx} ${cy})`}/>
    <path d={`M${cx - 74} ${cy + 35} Q${cx - 21} ${cy - 71} ${cx + 77} ${cy - 14} Q${cx + 17} ${cy + 73} ${cx - 50} ${cy - 8} Q${cx + 3} ${cy - 48} ${cx + 35} ${cy + 5}`} fill="none" stroke="#bdccd0" strokeOpacity={.23 * (1 - shrink)} strokeWidth="1.2"/>
    {[[-152, -61], [-104, 73], [-17, -104], [83, 88], [144, -25], [37, 49], [-63, 2]].map(([dx, dy], i) => <circle key={i} cx={cx + dx * (1 - shrink * .75)} cy={cy + dy * (1 - shrink * .75)} r={i % 3 === 0 ? 2.6 : 1.6} fill={i % 2 ? '#c5dfe2' : '#edcf91'} opacity={.22 + (1 - shrink) * .34}/>) }
    <circle cx={cx} cy={cy} r={10 + pulse(t, 3.2) * 8} fill="#eef5e7" opacity={.8}/>
    <circle cx={cx} cy={cy} r={26 + pulse(t, 3.2) * 8} fill="none" stroke="#d9e8dc" strokeOpacity={.42} strokeWidth="1.2"/>
  </g>;
};

const Island = ({x, y, scale = 1, right = false, t}: {x: number; y: number; scale?: number; right?: boolean; t: number}) => {
  const listening = right;
  return <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <ellipse cx="0" cy="126" rx="292" ry="69" fill="#05090a" opacity=".42"/>
    <path d="M-298 32 Q-273 -28 -205 -35 Q-151 -88 -70 -59 Q-3 -99 56 -61 Q139 -85 188 -38 Q273 -35 298 27 Q282 87 203 96 Q124 126 33 104 Q-51 131 -138 99 Q-238 105 -298 32Z" fill="#433423" stroke="#c59b63" strokeOpacity=".44" strokeWidth="2"/>
    <path d="M-277 22 Q-227 -22 -166 -18 Q-102 -72 -29 -45 Q34 -72 89 -42 Q166 -60 214 -12 Q267 0 275 32 Q226 74 153 67 Q69 95 7 67 Q-58 98 -134 68 Q-220 86 -277 22Z" fill="#26302b" stroke="#98a07b" strokeOpacity=".32" strokeWidth="1.4"/>
    <path d="M-263 29 Q-201 4 -143 17 Q-77 -10 -22 22 Q48 -7 111 20 Q176 2 254 30 M-215 55 Q-153 35 -101 49 Q-27 21 28 48 Q91 27 160 50" fill="none" stroke="#d0ad72" strokeOpacity=".22" strokeWidth="2"/>
    <path d="M-264 7 Q-252 -23 -228 -29 M-100 -43 Q-73 -59 -46 -50 M125 -39 Q152 -50 172 -34" fill="none" stroke="#e1b971" strokeOpacity=".55" strokeWidth="2" strokeLinecap="round"/>
    <path d="M-182 7 L-167 -28 L-143 5Z M-161 7 L-145 -38 L-119 10Z" fill="#111817" stroke="#b18959" strokeOpacity=".5" strokeWidth="1.5"/>
    <path d="M-172 -24 L-157 -12 L-145 -31 L-128 -14" fill="none" stroke="#e1b972" strokeOpacity=".4" strokeWidth="1.2"/>
    <path d="M195 18 L195 -28 L217 -44 L239 -28 L239 19 M190 -5 H245 M209 -30 V19 M226 -30 V19" fill="#18201d" stroke="#b18a5d" strokeOpacity=".65" strokeWidth="2"/>
    <path d="M187 -44 Q216 -64 246 -44" fill="none" stroke="#e1c18a" strokeOpacity=".58" strokeWidth="2"/>
    {[[-224, 20], [-207, 49], [-143, 41], [-110, 22], [-62, 58], [-15, 30], [46, 49], [112, 28], [160, 46], [230, 23]].map(([px, py], i) => <g key={i} opacity={.44 + pulse(t, .5, i) * .32}><circle cx={px} cy={py} r="3" fill={i % 3 === 0 ? '#f0c67f' : '#c1aa7e'}/><circle cx={px} cy={py} r="8" fill="#e8c17d" opacity=".12"/></g>)}
    {!listening ? <g>
      <path d="M-44 25 L-44 -92 L69 -92 L69 26 M-31 -75 H57 M-31 -58 H33 M-30 -41 H54" fill="#111614" stroke="#ad8e63" strokeOpacity=".68" strokeWidth="2"/>
      <path d="M-28 -71 H55 M-28 -54 H42 M-28 -37 H61" stroke="#d0ba91" strokeOpacity=".35" strokeWidth="1"/>
      <g transform="rotate(-8 -77 10)">
        <path d="M-138 -21 L-35 -31 L-22 31 L-126 39Z" fill="#b9a47f" stroke="#ecd6aa" strokeOpacity=".52" strokeWidth="1.5"/>
        <path d="M-126 -10 L-47 -18 M-121 0 L-42 -8 M-116 10 L-38 1" stroke="#5d594c" strokeOpacity=".5" strokeWidth="1.4"/>
        <path d="M-112 24 Q-94 4 -79 21 L-65 9 L-47 19" fill="none" stroke="#54645e" strokeWidth="1.5"/>
      </g>
      <text x="-88" y="-50" fill="#d8c8a5" fontFamily="serif" fontSize="13" opacity=".68">memory / image / form</text>
      <path d="M75 -13 Q100 -38 126 -14 Q151 8 131 32 Q106 49 82 29 Q62 7 75 -13Z" fill="none" stroke="#d6b77b" strokeOpacity=".72" strokeWidth="2"/>
      <path d="M78 3 Q104 -15 131 2 M104 -19 V26" fill="none" stroke="#d6b77b" strokeOpacity=".48" strokeWidth="1.3"/>
      <text x="80" y="56" fill="#dfcda7" fontFamily="serif" fontSize="14" opacity=".72">∫ x · p(x) dx</text>
      <path d="M-18 -104 Q-2 -114 15 -103 M3 -122 V-108" stroke="#c7a66d" strokeOpacity=".4" strokeWidth="1.5"/>
    </g> : <g>
      <path d="M-102 -12 L-102 -91 L107 -91 L107 -12" fill="#121917" stroke="#b18e61" strokeOpacity=".64" strokeWidth="2"/>
      <path d="M-79 -67 Q-39 -91 1 -61 M7 -56 Q37 -37 68 -69" fill="none" stroke="#e0cc9f" strokeOpacity=".72" strokeWidth="2.4"/>
      <path d="M3 -75 L3 -20 M-24 -48 L29 -48" stroke="#ac9b76" strokeOpacity=".58" strokeWidth="1.6"/>
      <circle cx="70" cy="-70" r="16" fill="none" stroke="#d0af73" strokeOpacity=".68" strokeWidth="1.6"/>
      <path d="M54 -70 H86 M70 -86 V-54" stroke="#d0af73" strokeOpacity=".53" strokeWidth="1"/>
      <path d="M-78 29 Q-69 -13 -48 -17 Q-28 -18 -23 12 L-12 42 M-51 -21 Q-55 -43 -39 -44 Q-21 -43 -26 -21 M-46 4 Q-60 13 -69 27" fill="none" stroke="#d0a57b" strokeWidth="8" strokeLinecap="round"/>
      <path d="M-48 -7 Q-18 -22 2 -7 M-32 -2 Q-3 -16 22 -1" fill="none" stroke="#d8b37a" strokeOpacity=".9" strokeWidth="2"/>
      <text x="-2" y="48" fill="#e0d0ac" fontFamily="serif" fontSize="13" opacity=".7">view 02</text>
    </g>}
    <path d="M-250 84 Q-192 61 -148 83 M118 81 Q166 66 213 83" fill="none" stroke="#e0bd7a" strokeOpacity=".43" strokeWidth="2"/>
  </g>;
};

const HumanArchipelago = ({t}: {t: number}) => {
  const arriving = smooth((t - 20) / 3.5);
  const rebuild = smooth((t - 28) / 2.4);
  const city = smooth((t - 34.5) / 3.6);
  const bridgePulse = .45 + pulse(t, 2.4) * .22;
  const packetX = 767 + (t >= 28 ? (t - 28) * 72 : (t - 20) * 60);
  const returningX = 1135 - clamp((t - 30) / 5) * 344;
  return <g>
    <defs>
      <linearGradient id="human-island-water" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#101b1b" stopOpacity=".2"/><stop offset=".55" stopColor="#0c1518" stopOpacity=".86"/><stop offset="1" stopColor="#161c1b" stopOpacity=".16"/></linearGradient>
      <linearGradient id="human-bridge" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#c99a59" stopOpacity=".1"/><stop offset=".5" stopColor="#f4ca80" stopOpacity=".9"/><stop offset="1" stopColor="#d0a76a" stopOpacity=".12"/></linearGradient>
      <radialGradient id="human-island-glow"><stop stopColor="#e7bd73" stopOpacity=".2"/><stop offset="1" stopColor="#dcaa62" stopOpacity="0"/></radialGradient>
    </defs>
    <path d="M110 764 Q358 684 588 739 T1040 730 T1460 739 T1810 687 L1810 850 L110 850Z" fill="url(#human-island-water)" opacity=".82"/>
    <ellipse cx="566" cy="573" rx="440" ry="275" fill="url(#human-island-glow)" opacity=".75"/>
    <ellipse cx="1348" cy="573" rx="440" ry="275" fill="url(#human-island-glow)" opacity=".55"/>
    <path d="M245 673 Q440 646 615 671 T985 674 M920 709 Q1100 675 1277 702 T1684 680" fill="none" stroke="#c59c65" strokeOpacity=".16" strokeWidth="1.2"/>

    <g opacity={1 - city * .12}>
      <Island x={555} y={571} t={t}/>
      <Island x={1365} y={568} right t={t}/>
    </g>

    <path d="M823 610 Q953 562 1090 608" fill="none" stroke="#171c1b" strokeWidth="25" strokeLinecap="round" opacity=".86"/>
    <path d="M824 601 Q953 551 1089 599" fill="none" stroke="url(#human-bridge)" strokeWidth="4" strokeOpacity={bridgePulse}/>
    <path d="M853 608 Q954 579 1061 605 M884 619 Q954 597 1028 617" fill="none" stroke="#bb9c6e" strokeOpacity=".38" strokeWidth="1.4"/>
    {[852, 908, 966, 1024, 1072].map((x, i) => <path key={i} d={`M${x} ${595 + Math.abs(960 - x) * .075} v-25`} stroke="#a68254" strokeOpacity=".52" strokeWidth="1.5"/>)}

    <g opacity={arriving}>
      <g transform={`translate(${packetX} ${582 - Math.sin(t * 1.3) * 9})`}>
        <path d="M-17 -14 L0 -23 L18 -13 L0 -4Z M-17 -14 V5 L0 15 V-4 M18 -13 V5 L0 15" fill="#e1bf7d" fillOpacity=".62" stroke="#ffe1a4" strokeWidth="1.4" strokeLinejoin="round"/>
        <circle cx="0" cy="-4" r="28" fill="url(#human-island-glow)"/>
      </g>
      <g transform={`translate(${packetX - 68} ${552 + Math.sin(t * 1.1) * 9})`} opacity=".84">
        <path d="M-12 6 Q0 -15 13 6 Q0 16 -12 6Z" fill="none" stroke="#deceb0" strokeWidth="1.5"/>
        <circle cx="0" cy="6" r="3" fill="#efcd8d"/>
      </g>
      <text x={packetX - 27} y="535" fill="#ddc799" fontFamily="serif" fontSize="13" letterSpacing="1" opacity=".7">∴</text>
    </g>
    <g opacity={rebuild} transform={`translate(${rebuild * 5} 0)`}>
      <path d="M1284 486 Q1314 457 1348 475 Q1375 490 1386 520 M1386 529 Q1372 556 1343 557 Q1314 554 1294 535" fill="none" stroke="#d6c090" strokeWidth="2.4" strokeLinecap="round"/>
      <path d="M1289 487 Q1321 466 1345 486 Q1372 503 1377 519 M1375 533 Q1353 548 1332 543 Q1318 540 1307 526" fill="none" stroke="#dfb975" strokeOpacity=".72" strokeWidth="1.2" strokeDasharray="3 4"/>
      <circle cx="1374" cy="525" r="23" fill="none" stroke="#e7c586" strokeOpacity=".76" strokeWidth="1.8"/>
      <path d="M1351 525 H1397 M1374 502 V548" stroke="#e7c586" strokeOpacity=".58" strokeWidth="1.1"/>
      <path d="M1345 480 L1363 468 M1381 540 L1397 553" stroke="#f3d79f" strokeWidth="2" strokeLinecap="round" opacity=".8"/>
    </g>
    <g opacity={smooth((t - 30) / 1.8)}>
      <path d={`M1130 612 Q${(1130 + returningX) / 2} 566 ${returningX} 611`} fill="none" stroke="#d3b276" strokeOpacity=".48" strokeWidth="1.5" strokeDasharray="3 7"/>
      <circle cx={returningX} cy="611" r="5" fill="#f2d190" opacity=".8"/>
    </g>

    <g opacity={city}>
      <path d="M286 625 Q322 576 365 587 Q403 554 447 574 Q496 550 533 578 Q585 554 626 589 Q669 580 706 619" fill="#19201e" stroke="#aa885b" strokeOpacity=".52" strokeWidth="1.6"/>
      <path d="M345 592 V523 L376 493 L405 520 V588 M405 585 V541 L435 516 L464 540 V586 M475 585 V501 L508 468 L542 502 V588 M543 588 V537 L571 512 L600 536 V589" fill="#131b19" stroke="#b99967" strokeOpacity=".7" strokeWidth="2"/>
      <path d="M357 545 H394 M419 554 H450 M490 524 H526 M555 550 H588" stroke="#e2bd7c" strokeOpacity=".49" strokeWidth="3"/>
      <path d="M479 467 Q508 435 538 468 M514 440 V414" fill="none" stroke="#d1aa70" strokeOpacity=".58" strokeWidth="1.6"/>
      <path d="M1128 686 Q1183 651 1249 672 T1372 672 T1516 679" fill="none" stroke="#d6b574" strokeOpacity=".36" strokeWidth="2"/>
      <path d="M621 705 Q792 658 900 690 Q1028 651 1154 696" fill="none" stroke="#cfaa6d" strokeOpacity=".45" strokeWidth="2.5"/>
      <path d="M699 705 Q747 683 790 693 M915 689 Q964 668 1007 685" fill="none" stroke="#f0ce8b" strokeOpacity=".48" strokeWidth="2"/>
      <g transform="translate(1064 687) rotate(-11)">
        <path d="M-89 -8 L58 -8 L74 43 L-76 43Z" fill="#c3ad87" stroke="#e6d0a3" strokeOpacity=".7" strokeWidth="1.5"/>
        <path d="M-64 6 L-8 6 M-64 16 L12 16 M-64 26 L-21 26 M21 4 L49 32 M49 4 L21 32" stroke="#56584d" strokeOpacity=".66" strokeWidth="1.4"/>
      </g>
      <path d="M1107 649 Q1235 595 1345 634 M1153 652 Q1254 613 1329 638" fill="none" stroke="#d0af75" strokeOpacity=".33" strokeWidth="1.5"/>
      <circle cx="1130" cy="638" r="4" fill="#f0cf8a"/><circle cx="1325" cy="646" r="4" fill="#e6c47f"/>
      <path d="M263 764 Q450 739 617 762 M774 765 Q956 737 1109 763 M1220 774 Q1437 739 1665 766" fill="none" stroke="#e1bd7d" strokeOpacity=".22" strokeWidth="1.2"/>
    </g>
    <path d="M186 792 Q440 758 653 791 M1150 794 Q1450 757 1774 786" fill="none" stroke="#d8b679" strokeOpacity=".16" strokeWidth="2"/>
  </g>;
};

const DialogueInput = ({t}: {t: number}) => {
  const opacity = window(t, 171, 176, .8);
  const caret = t < 173.2 || pulse(t, 2.8) > .44;
  return <g opacity={opacity}>
    <path d="M110 150 H1810 V850 H110Z" fill="#0a1113" fillOpacity=".68"/>
    <path d="M280 263 Q886 236 1571 272 L1654 714 Q959 738 346 705Z" fill="#182225" fillOpacity=".64" stroke="#c4b089" strokeOpacity=".17" strokeWidth="2"/>
    <path d="M351 333 Q958 314 1513 337 L1553 670 Q1009 687 385 665Z" fill="#0b1113" fillOpacity=".67"/>
    <g opacity=".28">
      <circle cx="1253" cy="428" r="2" fill="#d5decc"/><circle cx="1318" cy="396" r="1.5" fill="#e2c992"/><circle cx="1406" cy="455" r="1.7" fill="#cad9d5"/>
      <path d="M1254 429 Q1290 375 1318 397 T1405 455" fill="none" stroke="#c6c6a4" strokeWidth=".8"/>
      <path d="M1302 498 Q1340 452 1400 482" fill="none" stroke="#a6b7b4" strokeWidth=".7"/>
    </g>
    <rect x="520" y="470" width="880" height="94" rx="47" fill="#0d1517" fillOpacity=".94" stroke="#d4bf97" strokeOpacity=".47" strokeWidth="1.6"/>
    <path d="M567 470 V564" stroke="#e0c38e" strokeOpacity={caret ? .86 : .12} strokeWidth="2"/>
    <text x="594" y="529" fill="#e5dcc9" fontFamily="PingFang SC, sans-serif" fontSize="24" letterSpacing="1.4" opacity=".72">问一个问题…</text>
    <circle cx="1351" cy="517" r="24" fill="#d6bd8d" fillOpacity=".12" stroke="#d7bd8d" strokeOpacity=".34" strokeWidth="1"/>
    <path d="M1341 517 H1361 M1351 507 V527" stroke="#e1d3b4" strokeOpacity=".68" strokeWidth="1.4"/>
    <path d="M648 629 Q962 648 1274 626" fill="none" stroke="#d9c49d" strokeOpacity=".13" strokeWidth="1"/>
  </g>;
};

const Ending = ({t}: {t: number}) => {
  const inFrame = smooth((t - 176) / .9);
  const hold = clamp((t - 177) / 1.5);
  const ringLength = 388;
  const drawn = Math.min(ringLength, Math.max(0, (t - 176.1) * 300));
  return <g opacity={inFrame}>
    <path d="M110 150 H1810 V850 H110Z" fill="#080e11" fillOpacity=".82"/>
    <g opacity=".4" fill="#d7d0b6">
      {[[333,270],[481,376],[1457,246],[1539,666],[1268,741],[649,730],[1584,422],[291,583],[1020,221],[1114,755],[1692,322],[741,258]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i%4===0?2:1.35} opacity={.25+((i%3)*.18)}/>)}
    </g>
    <g transform="rotate(-13 689 494)">
      <circle cx="689" cy="486" r="152" fill="none" stroke="#c8e0df" strokeOpacity=".075" strokeWidth="1"/>
      <path d="M689 334 A152 152 0 1 1 581 593" fill="none" stroke="#d3e6df" strokeOpacity=".18" strokeWidth="1.2" strokeDasharray="2 8"/>
      <path d="M689 338 A148 148 0 1 1 590 587" fill="none" stroke="#dcece0" strokeWidth="7" strokeLinecap="round" strokeDasharray={`${drawn} ${ringLength}`}/>
      <path d="M591 586 L555 624 L608 616" fill="none" stroke="#e5f0df" strokeOpacity={hold * .85} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="689" cy="338" r="5" fill="#f1f2dd" opacity={inFrame}/>
    </g>
    <ellipse cx="690" cy="488" rx="251" ry="225" fill="url(#human-island-glow)" opacity=".5"/>
    <path d="M884 391 V614" stroke="#d7d1bd" strokeOpacity=".25" strokeWidth="1"/>
    <text x="964" y="462" fill="#f0e7d5" fontFamily="PingFang SC, sans-serif" fontSize="52" fontWeight="400" letterSpacing="11" opacity={smooth((t - 176.7) / .8)}>十万亿个分身</text>
    <path d="M965 507 H1409" stroke="#d3be91" strokeOpacity=".33" strokeWidth="1.3"/>
    <text x="968" y="555" fill="#c8c9bd" fontFamily="PingFang SC, sans-serif" fontSize="23" letterSpacing="4" opacity={smooth((t - 177.2) / .8)}>余问  QStory</text>
    <text x="968" y="605" fill="#8e9ba2" fontFamily="PingFang SC, sans-serif" fontSize="19" letterSpacing="2" opacity={smooth((t - 177.7) / .8)}>科幻思想实验 · 待真实实验验证</text>
    <circle cx="1457" cy="550" r="2.2" fill="#e2cca0" opacity={.35 + pulse(t, .62) * .2}/>
  </g>;
};

/** Human-side story for EP.03. `t` is always the global film time in seconds. */
export const HumanScene: React.FC<HumanSceneProps> = ({t}) => {
  if (!Number.isFinite(t) || t < 0 || (t >= 42 && t < 165) || t >= 180) return <g/>;
  const opening = t < 12.5 ? 1 - smooth((t - 10.2) / 2.3) : 0;
  const islands = window(t, 11.4, 42.1, 2.8);
  const returnDesk = t >= 165 && t < 171.4 ? 1 - smooth((t - 170.4) / 1) : 0;
  const input = t >= 170.5 && t < 176.1 ? 1 : 0;
  const end = t >= 175.5 ? 1 : 0;
  return <g>
    <g opacity={opening}><Desk t={t}/><SoundPrelude t={t}/></g>
    <g opacity={islands}><HumanArchipelago t={t}/></g>
    <g opacity={returnDesk}><Desk t={t} returning/></g>
    {input ? <DialogueInput t={t}/> : null}
    {end ? <Ending t={t}/> : null}
  </g>;
};
