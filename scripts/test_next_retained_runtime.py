"""Retained runtime privacy/move/limit guards; real kernel enforcement remains a CI gate."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from next_retained_runtime import ProducerMoves,check_container,check_limits,MEMORY_BYTES,PROBE_NODE

class RetainedRuntimeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(tempfile.mkdtemp(prefix="retained-next-controls-",dir=os.environ["PATAMAPS_TEST_RETAIN_ROOT"]))
    def case(self):
        work=self.root/self._testMethodName;work.mkdir()
        private=work/"private";private.mkdir()
        return work,private
    def container(self,role="app"):
        return dict(Image="sha256:controlled",Config=dict(User="1000:1000",WorkingDir="/bundle",
            Entrypoint=["/usr/local/bin/node"] if role=="probe" else ["/usr/local/bin/node","/bundle/server.js"],
            Cmd=["-e",PROBE_NODE] if role=="probe" else []),Mounts=[],
            HostConfig=dict(ReadonlyRootfs=True,NetworkMode="host",Binds=None,NanoCpus=1000000000,
                Memory=MEMORY_BYTES,MemorySwap=MEMORY_BYTES,PidsLimit=128,CapDrop=["ALL"],
                SecurityOpt=["no-new-privileges"],Privileged=False,Devices=[],DeviceRequests=[],
                Tmpfs={"/bundle/.next/cache":"rw,noexec,nosuid,nodev,size=67108864,mode=0700,uid=1000,gid=1000"}))
    def test_nested_source_and_dependency_moves_restore_exact_bytes(self):
        work,private=self.case();owner=work/"owner";(owner/"node_modules/pkg").mkdir(parents=True)
        (owner/"node_modules/pkg/value").write_bytes(b"\x00bound-package")
        (owner/"source.ts").write_text("bound source")
        harness=work/"harness";harness.mkdir();moves=ProducerMoves(private)
        moves.take(owner/"node_modules",harness/"node_modules");moves.take(owner)
        self.assertFalse(owner.exists());self.assertEqual((harness/"node_modules/pkg/value").read_bytes(),b"\x00bound-package")
        moves.restore()
        self.assertEqual((owner/"source.ts").read_text(),"bound source")
        self.assertEqual((owner/"node_modules/pkg/value").read_bytes(),b"\x00bound-package")
        self.assertFalse((harness/"node_modules").exists())
    def test_restore_conflict_preserves_both_versions(self):
        work,private=self.case();original=work/"producer";original.write_text("original")
        moves=ProducerMoves(private);moves.take(original);original.write_text("new conflicting file")
        with self.assertRaisesRegex(AssertionError,"RESTORATION_REQUIRES_REVIEW"):moves.restore()
        self.assertEqual(original.read_text(),"new conflicting file")
        self.assertEqual(moves.items[0][1].read_text(),"original")
    def test_move_refuses_existing_destination_without_overwrite(self):
        work,private=self.case();original=work/"producer";destination=work/"retained"
        original.write_text("original");destination.write_text("preserve destination")
        with self.assertRaisesRegex(AssertionError,"PRECONDITION"):ProducerMoves(private).take(original,destination)
        self.assertEqual(original.read_text(),"original");self.assertEqual(destination.read_text(),"preserve destination")
    def test_symbolic_tool_alias_is_restored_without_touching_target(self):
        work,private=self.case();program=work/"program";program.write_text("program")
        alias=work/"configured-build-tool";alias.symlink_to(program)
        moves=ProducerMoves(private);moves.take(alias)
        self.assertFalse(alias.exists());self.assertEqual(program.read_text(),"program")
        moves.restore()
        self.assertTrue(alias.is_symlink());self.assertEqual(os.readlink(alias),str(program))
    def test_valid_declared_app_and_probe_configurations(self):
        check_container(self.container(),"sha256:controlled","app")
        check_container(self.container("probe"),"sha256:controlled","probe")
        check_limits(dict(cpu="100000 100000",memory=str(MEMORY_BYTES),swap="0",pids="128"))
    def test_unbounded_or_privileged_container_configs_refuse(self):
        variants=[
            ("ReadonlyRootfs",False),("NanoCpus",0),("Memory",0),("MemorySwap",-1),("PidsLimit",0),
            ("Privileged",True),("CapDrop",[]),("SecurityOpt",[]),("Devices",[{"PathOnHost":"/dev/controlled"}]),
            ("DeviceRequests",[{"Driver":"controlled"}]),("NetworkMode","bridge"),
            ("Binds",["/controlled/source:/bundle"]),("Mounts",[{"Type":"bind","Source":"/controlled"}]),
            ("Tmpfs",{"/bundle/.next/cache":"rw,size=134217728"}),
        ]
        for key,value in variants:
            with self.subTest(key=key):
                info=self.container();info["HostConfig"][key]=value
                with self.assertRaises(AssertionError):check_container(info,"sha256:controlled","app")
    def test_inspected_extra_mount_or_changed_entrypoint_refuses(self):
        info=self.container();info["Mounts"]=[dict(Type="bind",Destination="/bundle")]
        with self.assertRaisesRegex(AssertionError,"MOUNTS"):check_container(info,"sha256:controlled","app")
        info=self.container();info["Config"]["Entrypoint"]=["/bin/sh"]
        with self.assertRaisesRegex(AssertionError,"ENTRYPOINT"):check_container(info,"sha256:controlled","app")
        info=self.container("probe");info["Config"]["Cmd"]=["-e","changed program"]
        with self.assertRaisesRegex(AssertionError,"ENTRYPOINT"):check_container(info,"sha256:controlled","probe")
    def test_actual_kernel_limit_mismatches_refuse(self):
        valid=dict(cpu="100000 100000",memory=str(MEMORY_BYTES),swap="0",pids="128")
        for key,bad in [("cpu","max 100000"),("memory","max"),("swap","max"),("pids","max")]:
            value=copy.deepcopy(valid);value[key]=bad
            with self.subTest(key=key):
                with self.assertRaisesRegex(AssertionError,"KERNEL_LIMITS"):check_limits(value)

if __name__=="__main__":unittest.main()
