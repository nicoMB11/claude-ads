// SoleilIntro.tsx — Intro MOTION DESIGN pour Soleil (soleil-bijoux.com)
// Overlay plein écran : fond de lumière dorée vivante + typographie cinétique,
// puis révélation "en lamelles" qui ouvre ton site derrière. Se joue 1×/session.
// 100% autonome (aucune dépendance). Couleurs + typo = DA Soleil.
//
// Intégration Lovable :
//   1) Place ce fichier dans src/components/SoleilIntro.tsx
//   2) Dans src/App.tsx, rends-le tout en haut de l'arbre :
//        import SoleilIntro from "@/components/SoleilIntro";
//        return (<><SoleilIntro /> {/* le reste de ton app */}</>);
//   3) Ajoute les polices dans index.html (<head>) :
//        <link rel="preconnect" href="https://fonts.googleapis.com">
//        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
//        <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;1,9..144,300&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
//
// Rejouer l'intro depuis n'importe quel bouton :
//        import { replaySoleilIntro } from "@/components/SoleilIntro";
//        <button onClick={replaySoleilIntro}>Revoir l'intro</button>

import { useEffect, useRef } from "react";

export function replaySoleilIntro() {
  window.dispatchEvent(new Event("soleil:replay"));
}

const BANDS = 7;

const CSS = `
.si-overlay{
  --cream:#FBF7EE; --sand:#EFE5D2; --terracotta:#C77456; --gold:#D2A24C; --ink:#3A3027;
  position:fixed; inset:0; z-index:99999; overflow:hidden;
  font-family:'Inter',system-ui,sans-serif; color:var(--ink);
}
.si-overlay.gone{ display:none; }

/* living golden-light background, built from horizontal bands that open like blinds */
.si-bands{ position:absolute; inset:0; z-index:0; }
.si-band{
  position:absolute; left:0; width:100%; height:calc(100% / ${BANDS} + 1px);
  background:linear-gradient(165deg,#FCF8EF 0%,#F4EAD4 52%,#EAD6B0 100%);
  background-attachment:fixed; background-size:100vw 100vh; background-position:center;
  transform:scaleY(1); transition:transform .9s cubic-bezier(.76,0,.24,1); will-change:transform;
}
.si-band:nth-child(odd){ transform-origin:top; }
.si-band:nth-child(even){ transform-origin:bottom; }

.si-glow{
  position:absolute; inset:-20%; z-index:1; pointer-events:none; mix-blend-mode:screen;
  filter:blur(48px); opacity:.9;
  background:
    radial-gradient(38% 38% at 28% 30%, rgba(210,162,76,.62), transparent 60%),
    radial-gradient(42% 42% at 76% 68%, rgba(199,116,86,.42), transparent 62%),
    radial-gradient(30% 30% at 60% 22%, rgba(255,240,205,.5), transparent 60%);
  animation:si-drift 16s ease-in-out infinite alternate;
}
@keyframes si-drift{ 0%{transform:translate(-3%,-2%) scale(1)} 50%{transform:translate(4%,3%) scale(1.08)} 100%{transform:translate(-2%,4%) scale(1.04)} }

.si-grain{
  position:absolute; inset:-50%; z-index:2; pointer-events:none; opacity:.045; mix-blend-mode:multiply;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
  animation:si-gr 1.1s steps(3) infinite;
}
@keyframes si-gr{ 0%{transform:translate(0,0)} 33%{transform:translate(-4%,3%)} 66%{transform:translate(3%,-2%)} 100%{transform:translate(0,0)} }

/* kinetic type stage */
.si-seq{ position:absolute; inset:0; z-index:3; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:24px; }
.si-line{ overflow:hidden; display:block; padding:.06em 0; }
.si-line > span{ display:inline-block; transform:translateY(118%); will-change:transform; }
.si-kicker{ margin-bottom:clamp(18px,3vw,30px); }
.si-eyebrow{ font:500 11px/1 'Inter'; text-transform:uppercase; letter-spacing:.5em; color:var(--terracotta); }
.si-claim{ font-family:'Fraunces',serif; font-weight:300; color:var(--ink); font-size:clamp(40px,7.4vw,92px); line-height:1.02; letter-spacing:-.012em; margin:0; }
.si-claim em{ font-style:italic; color:var(--terracotta); }
.si-word-stage{ position:absolute; display:flex; flex-direction:column; align-items:center; gap:.18em; opacity:0; }
.si-word{ font-family:'Fraunces',serif; font-weight:300; color:var(--ink); font-size:clamp(74px,15vw,200px); line-height:.9; letter-spacing:-.02em; position:relative; }
.si-word .si-sheen{
  position:absolute; inset:0; background:linear-gradient(105deg,transparent 38%,rgba(255,255,255,.85) 50%,transparent 62%);
  background-size:280% 100%; background-position:200% 0;
  -webkit-background-clip:text; background-clip:text; color:transparent; -webkit-text-fill-color:transparent;
  mix-blend-mode:screen; pointer-events:none;
}
.si-uline{ width:0; height:2px; border-radius:2px; background:linear-gradient(90deg,transparent,var(--gold) 20%,var(--terracotta) 80%,transparent); }

.si-skip{
  position:absolute; right:24px; bottom:22px; z-index:7;
  font:500 11px/1 'Inter'; letter-spacing:.22em; text-transform:uppercase; color:var(--ink);
  opacity:.5; cursor:pointer; background:none; border:0; display:flex; align-items:center; gap:8px; transition:opacity .3s;
}
.si-skip:hover{ opacity:1; }
.si-skip::after{ content:""; width:24px; height:1px; background:currentColor; }

/* ---- TIMELINE ---- */
@keyframes si-rise{ to{ transform:translateY(0) } }
@keyframes si-fall{ to{ transform:translateY(-118%) } }
.si-overlay.play .si-kicker .si-line>span{ animation:si-rise .9s cubic-bezier(.2,.85,.25,1) .35s forwards, si-fall .8s cubic-bezier(.7,0,.3,1) 2.5s forwards; }
.si-overlay.play .si-claim.l1 .si-line>span{ animation:si-rise 1s cubic-bezier(.2,.85,.25,1) .65s forwards, si-fall .85s cubic-bezier(.7,0,.3,1) 2.55s forwards; }
.si-overlay.play .si-claim.l2 .si-line>span{ animation:si-rise 1s cubic-bezier(.2,.85,.25,1) .9s forwards, si-fall .85s cubic-bezier(.7,0,.3,1) 2.62s forwards; }

.si-overlay.play .si-word-stage{ animation:si-wordin 1.1s cubic-bezier(.16,.84,.3,1) 3.0s forwards; }
@keyframes si-wordin{ 0%{opacity:0;transform:translateY(18px) scale(.96);filter:blur(10px)} 100%{opacity:1;transform:translateY(0) scale(1);filter:blur(0)} }
.si-overlay.play .si-uline{ animation:si-draw .9s cubic-bezier(.7,0,.2,1) 3.5s forwards; }
@keyframes si-draw{ to{ width:min(62vw,560px) } }
.si-overlay.play .si-word .si-sheen{ animation:si-sheen 1.1s ease 3.7s forwards; }
@keyframes si-sheen{ 0%{background-position:200% 0} 100%{background-position:-120% 0} }

/* REVEAL — blinds open + word lifts away */
.si-overlay.reveal .si-word-stage{ animation:si-wordout .7s cubic-bezier(.6,0,.2,1) forwards; }
@keyframes si-wordout{ to{opacity:0;transform:translateY(-26px) scale(1.03);filter:blur(4px)} }
.si-overlay.reveal .si-band{ transform:scaleY(0); }
.si-overlay.reveal .si-band:nth-child(1){ transition-delay:0s }
.si-overlay.reveal .si-band:nth-child(2){ transition-delay:.07s }
.si-overlay.reveal .si-band:nth-child(3){ transition-delay:.14s }
.si-overlay.reveal .si-band:nth-child(4){ transition-delay:.21s }
.si-overlay.reveal .si-band:nth-child(5){ transition-delay:.28s }
.si-overlay.reveal .si-band:nth-child(6){ transition-delay:.35s }
.si-overlay.reveal .si-band:nth-child(7){ transition-delay:.42s }
.si-overlay.reveal .si-glow, .si-overlay.reveal .si-grain{ opacity:0; transition:opacity .5s ease; }

@media (prefers-reduced-motion: reduce){ .si-overlay *{ animation:none !important; transition:none !important; } }
`;

export default function SoleilIntro() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const SEEN = "soleil_intro_seen";
    const seen = () => { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return false; } };
    const mark = () => { try { sessionStorage.setItem(SEEN, "1"); } catch {} };

    let timers: number[] = [];
    const at = (t: number, f: () => void) => { timers.push(window.setTimeout(f, t)); };
    const clr = () => { timers.forEach(clearTimeout); timers = []; };
    const lock = () => { document.body.style.overflow = "hidden"; };
    const unlock = () => { document.body.style.overflow = ""; };

    const toLive = () => { clr(); root.classList.remove("play", "reveal"); root.classList.add("gone"); unlock(); };

    const finish = () => {
      if (root.classList.contains("reveal")) return;
      clr(); mark();
      root.classList.add("reveal");
      at(1450, () => { root.classList.add("gone"); unlock(); });
    };

    const play = () => {
      clr(); lock();
      root.classList.remove("gone", "reveal");
      root.classList.remove("play"); void root.offsetWidth; // restart keyframes
      requestAnimationFrame(() => root.classList.add("play"));
      at(4400, finish);
    };

    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" || e.key === "Enter") finish(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("soleil:replay", play);
    window.addEventListener("soleil:skip", finish);

    if (reduce || seen()) toLive(); else play();

    return () => {
      clr();
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("soleil:replay", play);
      window.removeEventListener("soleil:skip", finish);
      unlock();
    };
  }, []);

  return (
    <>
      <style>{CSS}</style>
      <div ref={rootRef} className="si-overlay" aria-hidden="true">
        <div className="si-bands">
          {Array.from({ length: BANDS }).map((_, i) => (
            <div
              key={i}
              className="si-band"
              style={{ top: `calc(${i} * 100% / ${BANDS})` }}
            />
          ))}
        </div>
        <div className="si-glow" />
        <div className="si-grain" />
        <div className="si-seq">
          <div className="si-kicker">
            <span className="si-line"><span className="si-eyebrow">Été 2026 — Drop colliers</span></span>
          </div>
          <p className="si-claim l1"><span className="si-line"><span>Le style d'été,</span></span></p>
          <p className="si-claim l2"><span className="si-line"><span><em>à petit prix.</em></span></span></p>
          <div className="si-word-stage">
            <div className="si-word">soleil<span className="si-sheen">soleil</span></div>
            <div className="si-uline" />
          </div>
        </div>
        <button
          className="si-skip"
          onClick={() => window.dispatchEvent(new Event("soleil:skip"))}
          aria-label="Entrer"
        >
          Entrer
        </button>
      </div>
    </>
  );
}
