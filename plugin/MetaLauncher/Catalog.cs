using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace MetaLauncher {
    internal sealed class MetaCommand {
        public string Label;  // e.g. "!continue"
        public string Send;   // exact chat line, e.g. "/f !continue"
    }

    internal sealed class MetaEntry {
        public string Tab, Name, Title, Status, Author, Notes;
        public bool Fellowship, NeedsTownNetworkTie;
        public List<MetaCommand> Commands = new List<MetaCommand>();
        public bool IsDraft { get { return Status == "draft"; } }
    }

    // Reads catalog.tsv written by tools/build.py (see write_catalog_tsv there for the columns).
    internal sealed class Catalog {
        public List<string> Tabs = new List<string>();
        public List<MetaEntry> Metas = new List<MetaEntry>();

        public const string MyMetasTab = "My Metas";
        private const string VirindiTankKey = @"SOFTWARE\Decal\Plugins\{642F1F48-16BE-48BF-B1D4-286652C4533E}";
        private const string DefaultVirindiTankDir = @"C:\Games\VirindiPlugins\VirindiTank";

        // VirindiTank's folder, as Decal knows it (acclient is 32-bit, so this reads the WOW6432Node view).
        public static string VirindiTankDir() {
            try {
                using (var key = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(VirindiTankKey)) {
                    var path = key == null ? null : key.GetValue("Path") as string;
                    if (!string.IsNullOrEmpty(path) && Directory.Exists(path)) return path;
                }
            }
            catch { }
            return DefaultVirindiTankDir;
        }

        // Every .met in the VirindiTank folder that the bundle doesn't list goes on the My Metas tab.
        public void AddLocalMetas(string dir) {
            var known = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var meta in Metas) known.Add(meta.Name);
            var local = new List<MetaEntry>();
            if (Directory.Exists(dir)) {
                foreach (var file in Directory.GetFiles(dir, "*.met")) {
                    string name = Path.GetFileNameWithoutExtension(file);
                    if (known.Contains(name)) continue;
                    local.Add(new MetaEntry { Tab = MyMetasTab, Name = name, Title = name, Status = "local", Author = "", Notes = "" });
                }
            }
            local.Sort((a, b) => string.Compare(a.Title, b.Title, StringComparison.OrdinalIgnoreCase));
            Metas.AddRange(local);
            Tabs.Add(MyMetasTab);
        }

        public static Catalog Load(string path) {
            var catalog = new Catalog();
            foreach (var line in File.ReadAllLines(path, Encoding.UTF8)) {
                if (line.Length == 0) continue;
                var f = line.Split('\t');
                if (f[0] == "#tabs") {
                    for (int i = 1; i < f.Length; i++) catalog.Tabs.Add(f[i]);
                    continue;
                }
                if (f.Length < 9) continue;
                var meta = new MetaEntry {
                    Tab = f[0], Name = f[1], Title = f[2], Status = f[3], Author = f[4],
                    Fellowship = f[5] == "1", NeedsTownNetworkTie = f[6] == "1", Notes = f[8],
                };
                foreach (var pair in f[7].Split(';')) {
                    int eq = pair.IndexOf('=');
                    if (eq > 0) meta.Commands.Add(new MetaCommand { Label = pair.Substring(0, eq), Send = pair.Substring(eq + 1) });
                }
                catalog.Metas.Add(meta);
            }
            return catalog;
        }
    }
}
