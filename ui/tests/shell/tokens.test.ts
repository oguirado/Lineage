// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { text, source, app, isolateDom } from './helpers.ts';
isolateDom();
// Semantic inventory is bound to the emitted elements and their actual CSS custom properties.
// No token spelling, palette or framework is prescribed by SPEC_U21.
const roles = ['text','muted','link','error','success','focus'] as const;
type RGBA = [number,number,number,number];
function color(input: string): RGBA {
  const value = input.trim().toLowerCase();
  if (value === 'transparent') return [0,0,0,0];
  const hex = /^#([a-f0-9]{3,8})$/u.exec(value)?.[1];
  if (hex) {
    const h = hex.length <= 4 ? [...hex].map(x => x+x).join('') : hex;
    if (![6,8].includes(h.length)) throw Error('Unresolved color');
    return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16),h.length===8?parseInt(h.slice(6),16)/255:1];
  }
  const rgb = /^rgba?\((.*)\)$/u.exec(value)?.[1];
  if (rgb) {
    const parts = rgb.split(/[,\s/]+/u).filter(Boolean);
    const values = parts.map((s,i) => s.endsWith('%') ? Number(s.slice(0,-1)) * (i<3?2.55:0.01) : Number(s));
    if ((values.length===3 || values.length===4) && values.every(Number.isFinite)) return [values[0],values[1],values[2],values[3]??1];
  }
  throw Error(`Unresolved color: ${input}`);
}
function composite(fg: RGBA, bg: RGBA): RGBA {
  const a = fg[3] + bg[3]*(1-fg[3]);
  if (a === 0) return [0,0,0,0];
  return [0,1,2].map(i => (fg[i]*fg[3]+bg[i]*bg[3]*(1-fg[3]))/a).concat(a) as RGBA;
}
function contrast(a: RGBA, b: RGBA): number {
  const lum = (c: RGBA) => c.slice(0,3).map(v => {const x=v/255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4;})
    .reduce((sum,x,i) => sum+x*[0.2126,0.7152,0.0722][i],0);
  const x=lum(a), y=lum(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);
}
function resolveValue(element: Element, value: string, depth=0): string {
  if (depth > 20) throw Error('Cyclic color variable');
  return value.replace(/var\((--[\w-]+)(?:,\s*([^()]+))?\)/gu, (_all,key,fallback) => {
    let cursor: Element|null=element; let resolved='';
    while(cursor && !resolved) {resolved=getComputedStyle(cursor).getPropertyValue(key).trim();cursor=cursor.parentElement;}
    if (!resolved && !fallback) throw Error(`Unresolved variable ${key}`);
    return resolveValue(element,resolved||fallback,depth+1);
  });
}
function background(element: Element): RGBA {
  const chain: RGBA[]=[];let node: Element|null=element;
  while(node) {const c=color(resolveValue(node,getComputedStyle(node).backgroundColor));chain.push(c);if(c[3]===1)break;node=node.parentElement;}
  expect(chain.at(-1)?.[3], 'A used background must resolve to an opaque surface').toBe(1);
  return chain.reverse().reduce((bg,fg)=>composite(fg,bg),[0,0,0,0] as RGBA);
}
it('A25 contrast oracle rejects low contrast and unresolved tokens instead of omitting them', () => {
  expect(contrast(color('#777777'),color('#ffffff'))).toBeLessThan(4.5);
  expect(contrast(color('#000000'),color('#ffffff'))).toBeGreaterThanOrEqual(4.5);
  expect(()=>color('var(--absent)')).toThrow(); expect(()=>color('unresolved')).toThrow();
});
it.each(['light','dark'])('A24 A25 actual %s token palette covers every semantic text/background pair', async theme => {
  const css = ['tokens','base','shell'].map(n=>text(`ui/styles/${n}.css`)).join('\n');
  const style=document.createElement('style');style.textContent=css;document.head.append(style);
  try {
    const {root}=await app();
    const control=root.querySelector(`[data-lin-action="theme-${theme}"]`) as HTMLButtonElement;expect(control).not.toBeNull();control.click();
    const {renderStatePanel}=await source('ui/primitives.ts',['renderStatePanel']);
    const panelByState: Record<string, HTMLElement> = {};
    for(const state of ['loading','empty','no-match','ready','busy','queued','running','stalled','stale','error','completed','not-built']) {
      const panel=renderStatePanel({state,title:'Synthetic state',detail:'Synthetic explanation'});
      panelByState[state]=panel;root.querySelector('main')!.append(panel);
    }
    const tokenNames=[...new Set(css.match(/--[\w-]+(?=\s*:)/gu)??[])];expect(tokenNames.length).toBeGreaterThan(0);
    // Palette identifiers are implementation choices. Inventory actual rendered roles instead.
    const inventory: Record<string, Element|null> = {text: root.querySelector('h1'), muted: root.querySelector('[role="status"]'),
      link: root.querySelector('nav a'), error: panelByState.error, success: panelByState.completed, focus: control};
    for(const role of roles) expect(inventory[role], `Unbound semantic presentation ${role}`).not.toBeNull();
    const elements=Array.from(root.querySelectorAll<HTMLElement>('*')).filter(el => el.textContent?.trim() && !['OPTION','SELECT','SCRIPT','STYLE'].includes(el.tagName));
    expect(elements.length).toBeGreaterThan(0);
    for(const el of elements) {
      const fg=color(resolveValue(el,getComputedStyle(el).color));const bg=background(el);
      expect(contrast(composite(fg,bg),bg),`${theme} ${el.tagName} ${el.textContent?.slice(0,40)}`).toBeGreaterThanOrEqual(4.5);
    }
    expect(css).toMatch(/:focus(?:-visible)?/u);
    control.focus();
    const outline=getComputedStyle(control).outlineColor;
    if(outline && outline!=='currentcolor') expect(color(resolveValue(control,outline))[3]).toBeGreaterThan(0);
  } finally {style.remove();}
});

it('A24 theme selection changes actual used colors, not only a theme marker', async () => {
  const css=['tokens','base','shell'].map(n=>text(`ui/styles/${n}.css`)).join('\n');
  const style=document.createElement('style');style.textContent=css;document.head.append(style);
  try {
    const {root}=await app();
    const light=root.querySelector('[data-lin-action="theme-light"]') as HTMLButtonElement;
    const dark=root.querySelector('[data-lin-action="theme-dark"]') as HTMLButtonElement;
    expect(light).not.toBeNull();expect(dark).not.toBeNull();
    const snapshot=()=>[document.documentElement,document.body,...Array.from(root.querySelectorAll('*'))]
      .map(el=>[resolveValue(el,getComputedStyle(el).color),resolveValue(el,getComputedStyle(el).backgroundColor)]);
    light.click();const before=snapshot();dark.focus();dark.click();const after=snapshot();
    expect(after).not.toEqual(before);expect(document.activeElement).toBe(dark);
  } finally {style.remove();}
});
