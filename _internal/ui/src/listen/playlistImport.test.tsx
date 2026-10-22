import {renderToString} from 'react-dom/server';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
const h=vi.hoisted(()=>({chosen:'mine',mutations:[] as any[],invalidate:vi.fn(),setData:vi.fn(),importMusic:vi.fn()}));
vi.mock('@tanstack/react-query',()=>({
  useQueryClient:()=>({invalidateQueries:h.invalidate,setQueryData:h.setData}),
  useQuery:(q:any)=>({data:q.queryKey[0]==='music'?{mine:1,playlists:[],error:''}:{playlist:h.chosen}}),
  useMutation:(options:any)=>{const mutation={mutate:vi.fn(),isPending:false,options};h.mutations.push(mutation);return mutation;},
}));
vi.mock('@/listen/MyMusic',()=>({MY_MUSIC_KEY:['music-local'],useCanImportMusic:()=>true}));
vi.mock('@/studio/musicImport',()=>({importMusic:h.importMusic}));
vi.mock('sonner',()=>({toast:Object.assign(vi.fn(),{success:vi.fn(),error:vi.fn(),warning:vi.fn(),dismiss:vi.fn(),loading:vi.fn()})}));
import {usePlaylistChoice} from '@/listen/PlaylistChoice';
import {MUSIC_CHANGED_EVENT} from '@/listen/musicBed';
beforeEach(()=>{
  h.mutations=[];h.invalidate.mockClear();h.setData.mockClear();h.chosen='mine';
  h.importMusic.mockResolvedValue({result:{tracks:[{link:'local:new'}],added:[{link:'local:new'}],existing:[],failed:[]}});
  vi.stubGlobal('window',new EventTarget());
});
afterEach(()=>vi.unstubAllGlobals());
function hook(){let choice:any;function Probe(){choice=usePlaylistChoice('b');return null;}renderToString(<Probe/>);return choice;}
it('đang dùng Nhạc của tôi: thêm bài báo trình phát làm mới hàng nhạc',async()=>{
  const changed=vi.fn();window.addEventListener(MUSIC_CHANGED_EVENT,changed);
  await hook().addMusic();
  expect(h.setData).toHaveBeenCalled();
  expect(h.mutations[0].mutate).not.toHaveBeenCalled();
  expect(changed).toHaveBeenCalled();
});
it('đối chứng đang chọn off: thêm bài chọn mine, onSuccess có phát sự kiện',async()=>{
  h.chosen='off';const changed=vi.fn();window.addEventListener(MUSIC_CHANGED_EVENT,changed);
  await hook().addMusic();
  expect(h.mutations[0].mutate).toHaveBeenCalledWith(expect.objectContaining({playlist:'mine'}));
  const variables=h.mutations[0].mutate.mock.calls[0][0];
  h.mutations[0].options.onSuccess({playlist:'mine'},variables);
  expect(changed).toHaveBeenCalledTimes(1);
});
