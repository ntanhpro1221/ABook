import { expect, it } from 'vitest';
import { frameStats, analyseTrace } from './gallery_jank.mjs';
it('ngưỡng >20 ms và p99 không bỏ frame dài hay lượt đầu',()=>{
  expect(frameStats([16,20,21,100])).toMatchObject({frames:4,janky:2,jankPct:50,p99:100,max:100});
});
it('trace chọn đúng renderer, cửa sổ, elementCount và stack mẫu CPU',()=>{
  const events=[{name:'thread_name',pid:1,tid:2,args:{name:'CrRendererMain'}},{name:'jank-start',pid:1,tid:2,ts:1000},
    {name:'RunTask',pid:1,tid:2,ts:2000,dur:40000,ph:'X'},
    {name:'UpdateLayoutTree',pid:1,tid:2,ts:3000,dur:20000,ph:'X',args:{elementCount:500}},
    {name:'RunTask',pid:3,tid:2,ts:2000,dur:50000,ph:'X'},
    {name:'RunTask',pid:1,tid:2,ts:602000,dur:50000,ph:'X'},
    {name:'ProfileChunk',pid:1,args:{data:{cpuProfile:{nodes:[{id:1,callFrame:{functionName:'render'}}],samples:[1]},timeDeltas:[2000]}}}];
  const report=analyseTrace(events);expect(report.longTasks).toHaveLength(1);expect(report.style[0].elements).toBe(500);
  expect(report.cpuStacks[0]).toEqual({selfMs:2,stack:[{functionName:'render'}]});
});
