using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using Decal.Adapter;

[assembly: AssemblyTitle("Meta Launcher")]
[assembly: AssemblyVersion("0.1.0.0")]
[assembly: ComVisible(false)]
// Decal registers the plugin under this GUID; tools/build.py writes the same one into MetaLauncher.reg.
[assembly: Guid("4c1e5f0a-7d2b-4a8e-9b6f-3e2d1c0b9a87")]

namespace MetaLauncher {
    [FriendlyName("Meta Launcher")]
    public sealed class PluginCore : PluginBase {
        internal static string PluginDir;
        private LauncherView view;

        protected override void Startup() {
            try {
                PluginDir = System.IO.Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                CoreManager.Current.CharacterFilter.LoginComplete += OnLoginComplete;
            }
            catch (Exception ex) { Log(ex); }
        }

        protected override void Shutdown() {
            try {
                CoreManager.Current.CharacterFilter.LoginComplete -= OnLoginComplete;
                if (view != null) view.Dispose();
            }
            catch (Exception ex) { Log(ex); }
        }

        // The window is created after login, when VirindiViewService is ready to draw it.
        private void OnLoginComplete(object sender, EventArgs e) {
            try {
                var catalog = Catalog.Load(System.IO.Path.Combine(PluginDir, "catalog.tsv"));
                catalog.AddLocalMetas(Catalog.VirindiTankDir());
                view = new LauncherView(catalog);
            }
            catch (Exception ex) { Log(ex); }
        }

        [DllImport("Decal.dll")]
        private static extern int DispatchOnChatCommand(ref IntPtr str, int target);

        // Send a command as if the player typed it. Decal's DispatchOnChatCommand lets other plugins
        // (UtilityBelt's /ub, VirindiTank's /vt) handle it first; InvokeChatParser alone skips them and
        // the server answers "Unknown command". Same approach as Mag-Tools / UtilityBelt.
        internal static void Command(string cmd) {
            IntPtr bstr = Marshal.StringToBSTR(cmd);
            bool eaten;
            try { eaten = (DispatchOnChatCommand(ref bstr, 1) & 1) > 0; }
            finally { Marshal.FreeBSTR(bstr); }
            if (!eaten) CoreManager.Current.Actions.InvokeChatParser(cmd);
        }

        internal static void Chat(string message) {
            CoreManager.Current.Actions.AddChatText("[Meta Launcher] " + message, 5);
        }

        internal static void Log(Exception ex) {
            try {
                Chat("error: " + ex.Message + " (details in MetaLauncher\\errors.txt)");
                File.AppendAllText(System.IO.Path.Combine(PluginDir ?? ".", "errors.txt"),
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + ex + Environment.NewLine);
            }
            catch { }
        }
    }
}
