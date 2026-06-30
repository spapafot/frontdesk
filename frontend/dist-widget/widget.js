(function(){"use strict";(function(){const i=document.currentScript||function(){const t=document.getElementsByTagName("script");return t[t.length-1]}();if(!i)return;const a=i.dataset,l=a.siteKey||"",p=a.accent||"#0284c7",w=a.position==="bottom-left"?"bottom-left":"bottom-right",b=a.greeting||"Hi! How can I help you today?",h=new URL(i.src,location.href),v=(a.api||h.origin).replace(/\/$/,""),y=a.app||new URL("./app/index.html",h).href;if(!l){console.error("[chat-widget] missing data-site-key");return}const c=document.createElement("div");c.style.cssText="position:fixed;z-index:2147483000;";const d=c.attachShadow({mode:"open"});document.body.appendChild(c);const m=w==="bottom-left"?"left:20px;":"right:20px;",f=document.createElement("style");f.textContent=`
    .launcher {
      position: fixed; bottom: 20px; ${m}
      width: 56px; height: 56px; border-radius: 50%;
      background: ${p}; color: #fff; border: 0; cursor: pointer;
      box-shadow: 0 6px 20px rgba(0,0,0,.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform .15s ease;
    }
    .launcher:hover { transform: scale(1.05); }
    .launcher svg { width: 26px; height: 26px; fill: currentColor; }
    .frame-wrap {
      position: fixed; bottom: 88px; ${m}
      width: 380px; height: 560px; max-width: calc(100vw - 40px);
      max-height: calc(100vh - 120px);
      border-radius: 16px; overflow: hidden; background: #fff;
      box-shadow: 0 12px 40px rgba(0,0,0,.28);
      display: none;
    }
    .frame-wrap.open { display: block; }
    iframe { width: 100%; height: 100%; border: 0; }
    @media (max-width: 480px) {
      .frame-wrap {
        bottom: 0; right: 0; left: 0; width: 100vw; height: 100vh;
        max-width: 100vw; max-height: 100vh; border-radius: 0;
      }
    }
  `,d.appendChild(f);const r=document.createElement("div");r.className="frame-wrap";const s=document.createElement("iframe");s.title="Chat",s.allow="clipboard-write";const o=new URL(y);o.searchParams.set("key",l),o.searchParams.set("api",v),o.searchParams.set("accent",p),o.searchParams.set("greeting",b);const e=document.createElement("button");e.className="launcher",e.setAttribute("aria-label","Open chat");const u='<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>',C='<svg viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';e.innerHTML=u;let n=!1,x=!1;function g(t){n=t,r.classList.toggle("open",n),e.innerHTML=n?C:u,e.setAttribute("aria-label",n?"Close chat":"Open chat"),n&&!x&&(s.src=o.href,x=!0)}e.addEventListener("click",()=>g(!n)),window.addEventListener("message",t=>{t.data&&t.data.type==="wx-close"&&g(!1)}),r.appendChild(s),d.appendChild(r),d.appendChild(e)})()})();
