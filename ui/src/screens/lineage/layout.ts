import type { LineageTreeData } from './model.ts';
import { order } from './model.ts';

/** A bounded decorative overview. Relationship evidence lives in the list. */
export function drawTree(tree:LineageTreeData,visibleIds:ReadonlySet<string>,selectedId:string|null):SVGSVGElement {
  const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');
  const nodes=tree.nodes.filter(n=>visibleIds.has(n.agent_id)).sort(order);
  const width=800,height=Math.max(80,nodes.length*28+24);
  svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
  svg.setAttribute('width',String(width));svg.setAttribute('height',String(height));
  const points=new Map(nodes.map((n,i)=>[n.agent_id,{x:24+Math.min(n.generation,12)*50,y:24+i*28}]));
  for(const n of nodes) {
    const point=points.get(n.agent_id)!;
    for(const p of n.parents) {
      const parent=points.get(p);if(!parent) continue;
      const line=document.createElementNS(ns,'line');
      for(const [k,v] of Object.entries({x1:parent.x,y1:parent.y,x2:point.x,y2:point.y})) line.setAttribute(k,String(v));
      line.setAttribute('stroke','currentColor');svg.append(line);
    }
    const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',String(point.x));dot.setAttribute('cy',String(point.y));dot.setAttribute('r',n.agent_id===selectedId?'6':'4');dot.setAttribute('fill','currentColor');svg.append(dot);
  }
  return svg;
}
