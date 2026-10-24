using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using VirindiViewService;
using VirindiViewService.Controls;

namespace MetaLauncher {
    // The in-game window: tab buttons, a list of metas, a details panel, and buttons that type chat commands.
    internal sealed class LauncherView : IDisposable {
        private const int CommandButtons = 6;
        private const int WrapChars = 52;  // requirement lines wrap at about this width
        private const int IconId = 0x060012D3;  // stock "Virindi" icon (weenie 42857), shown in the title bar and Virindi bar
        private static readonly Color Warn = Color.FromArgb(255, 200, 120);

        private readonly Catalog catalog;
        private readonly HudView view;
        private readonly HudCheckBox wholeFellow, showDrafts;
        private readonly HudTextBox search;
        private readonly HudStaticText title, info, status, returnMeta;
        private readonly HudStaticText[] requirements = new HudStaticText[5];
        private readonly HudButton load, stop, start, setReturn;
        private readonly HudButton[] commandButtons = new HudButton[CommandButtons];
        private readonly List<HudButton> tabButtons = new List<HudButton>();
        private readonly HudList list;
        private readonly List<MetaEntry> rows = new List<MetaEntry>();
        private int currentTab;
        private MetaEntry selected;

        public LauncherView(Catalog catalog) {
            this.catalog = catalog;
            view = new HudView("Meta Launcher (Beta)", 340, 520, new ACImage(IconId));
            var layout = new HudFixedLayout();
            view.Controls.HeadControl = layout;

            wholeFellow = new HudCheckBox { Text = "Whole fellowship (/ub bc)", Checked = true };
            showDrafts = new HudCheckBox { Text = "Show drafts", Checked = false };
            layout.AddControl(wholeFellow, new Rectangle(5, 5, 175, 18));
            layout.AddControl(showDrafts, new Rectangle(185, 5, 145, 18));

            layout.AddControl(new HudStaticText { Text = "Search:" }, new Rectangle(5, 28, 50, 18));
            search = new HudTextBox();
            layout.AddControl(search, new Rectangle(55, 28, 275, 18));

            // Full-size buttons instead of a HudTabView: VVS draws tab labels tiny and dim.
            int tabWidth = 330 / Math.Max(1, catalog.Tabs.Count);
            for (int t = 0; t < catalog.Tabs.Count; t++) {
                var button = new HudButton();
                int index = t;
                button.Hit += (s, e) => ShowTab(index);
                layout.AddControl(button, new Rectangle(5 + tabWidth * t, 52, tabWidth - 4, 24));
                tabButtons.Add(button);
            }
            list = new HudList();
            list.AddColumn(typeof(HudStaticText), 300, null);
            list.Click += (s, row, col) => Select(row);
            layout.AddControl(list, new Rectangle(5, 80, 330, 180));

            title = new HudStaticText();
            info = new HudStaticText();
            layout.AddControl(title, new Rectangle(5, 266, 330, 16));
            layout.AddControl(info, new Rectangle(5, 284, 330, 16));
            for (int i = 0; i < requirements.Length; i++) {
                requirements[i] = new HudStaticText { TextColor = Warn };
                layout.AddControl(requirements[i], new Rectangle(5, 302 + 17 * i, 330, 16));
            }

            load = new HudButton { Text = "Load" };
            layout.AddControl(load, new Rectangle(5, 392, 105, 22));
            // /vt stop and /vt start switch VirindiTank off/on; the loaded meta stays loaded
            stop = new HudButton { Text = "Stop VTank" };
            layout.AddControl(stop, new Rectangle(115, 392, 105, 22));
            start = new HudButton { Text = "Start VTank" };
            layout.AddControl(start, new Rectangle(225, 392, 105, 22));
            for (int i = 0; i < CommandButtons; i++) {
                var button = new HudButton { Visible = false };
                int index = i;
                button.Hit += (s, e) => SendCommand(index);
                commandButtons[i] = button;
                // meta commands (e.g. !continue) in two rows of three under the Load button
                layout.AddControl(button, new Rectangle(5 + 110 * (i % 3), 418 + 24 * (i / 3), 105, 22));
            }

            // Most quest metas finish with "/vt meta load <defaultMeta>"; this picks what that loads.
            returnMeta = new HudStaticText();
            layout.AddControl(returnMeta, new Rectangle(5, 472, 220, 18));
            setReturn = new HudButton { Text = "Use selected" };
            layout.AddControl(setReturn, new Rectangle(230, 470, 100, 22));
            ShowReturnMeta(ReadReturnMeta());

            status = new HudStaticText();
            layout.AddControl(status, new Rectangle(5, 496, 330, 16));

            load.Hit += (s, e) => LoadSelected();
            stop.Hit += (s, e) => { Send("/vt stop"); status.Text = "VTank stopped" + (wholeFellow.Checked ? " (all clients)" : ""); };
            start.Hit += (s, e) => { Send("/vt start"); status.Text = "VTank started" + (wholeFellow.Checked ? " (all clients)" : ""); };
            setReturn.Hit += (s, e) => SetReturnMeta();
            showDrafts.Change += (s, e) => Refresh();
            search.Change += (s, e) => Refresh();

            ShowTab(0);
            ShowDetails();
        }

        private void ShowTab(int tab) {
            currentTab = tab;
            for (int t = 0; t < tabButtons.Count; t++)
                tabButtons[t].Text = t == tab ? "*" + catalog.Tabs[t] : catalog.Tabs[t];
            Refresh();
        }

        private void Refresh() {
            if (catalog.Tabs.Count == 0) return;
            string q = (search.Text ?? "").Trim().ToLowerInvariant();
            list.ClearRows();
            rows.Clear();
            foreach (var meta in catalog.Metas) {
                if (meta.Tab != catalog.Tabs[currentTab]) continue;
                if (meta.IsDraft && !showDrafts.Checked) continue;
                if (q.Length > 0 && !meta.Title.ToLowerInvariant().Contains(q) && !meta.Name.ToLowerInvariant().Contains(q)) continue;
                var row = list.AddRow();
                ((HudStaticText)row[0]).Text = meta.IsDraft ? meta.Title + "  (draft)" : meta.Title;
                rows.Add(meta);
            }
        }

        private void Select(int row) {
            if (row < 0 || row >= rows.Count) return;
            selected = rows[row];
            ShowDetails();
        }

        private void ShowDetails() {
            var items = new List<string>();
            if (selected == null) {
                title.Text = "Pick a meta from the list.";
                info.Text = "";
            }
            else {
                title.Text = selected.Title;
                info.Text = selected.Status == "local"
                    ? "Your own meta (VirindiTank folder, not checked by the bundle)"
                    : selected.Name + ".met   by " + selected.Author;
                if (selected.Fellowship) items.Add("Fellowship meta: the fellowship leader leads");
                if (selected.NeedsTownNetworkTie) items.Add("Needs a portal tie to a Town Network portal");
                if (selected.IsDraft) items.Add("DRAFT: never published by its author");
                if (!string.IsNullOrEmpty(selected.Notes)) items.AddRange(selected.Notes.Split(new[] { " | " }, StringSplitOptions.None));
            }
            var lines = Wrap(items);
            for (int i = 0; i < requirements.Length; i++)
                requirements[i].Text = i < lines.Count ? lines[i] : "";
            load.Visible = selected != null;
            for (int i = 0; i < CommandButtons; i++) {
                bool show = selected != null && i < selected.Commands.Count;
                commandButtons[i].Visible = show;
                if (show) commandButtons[i].Text = selected.Commands[i].Label;
            }
        }

        // "- item" lines of at most WrapChars, broken at spaces; continuation lines are indented.
        private static List<string> Wrap(List<string> items) {
            var lines = new List<string>();
            foreach (var item in items) {
                string rest = "- " + item;
                while (rest.Length > WrapChars) {
                    int cut = rest.LastIndexOf(' ', WrapChars);
                    if (cut < 10) cut = WrapChars;
                    lines.Add(rest.Substring(0, cut));
                    rest = "   " + rest.Substring(cut).TrimStart();
                }
                lines.Add(rest);
            }
            return lines;
        }

        private void LoadSelected() {
            if (selected == null) return;
            // The metas use UtilityBelt's extra expression functions (getqueststatus, ...). Some check them
            // in their first state, before their own Settings state turns the patch on, and a few never
            // turn it on, so switch it on first. Default in UB is off.
            Send("/ub opt set VTank.PatchExpressionEngine true");
            Send("/vt meta load " + selected.Name);
            status.Text = "Loaded: " + selected.Name + (wholeFellow.Checked ? " (all clients)" : "");
        }

        private void SendCommand(int index) {
            if (selected == null || index >= selected.Commands.Count) return;
            // Meta commands go out once, from this client: the meta on every client hears them in chat.
            PluginCore.Command(selected.Commands[index].Send);
        }

        // Sets UtilityBelt's defaultMeta variable to the selected meta, and remembers it for display.
        private void SetReturnMeta() {
            if (selected == null) {
                status.Text = "Pick a meta in the list first (My Metas has your own).";
                return;
            }
            string name = selected.Name;
            if (name.IndexOf('`') >= 0) {
                status.Text = "Can't use a meta whose name contains `";
                return;
            }
            Send("/ub mexec setgvar[defaultMeta,`" + name + "`]");
            ShowReturnMeta(name);
            try { File.WriteAllText(ReturnMetaFile, name); } catch (Exception ex) { PluginCore.Log(ex); }
            status.Text = "After a quest, metas will switch to " + name;
        }

        private static string ReturnMetaFile {
            get { return System.IO.Path.Combine(PluginCore.PluginDir, "returnmeta.txt"); }
        }

        private static string ReadReturnMeta() {
            try { return File.Exists(ReturnMetaFile) ? File.ReadAllText(ReturnMetaFile).Trim() : ""; }
            catch { return ""; }
        }

        private void ShowReturnMeta(string name) {
            returnMeta.Text = "After a quest, switch to: " + (name.Length > 0 ? name : "(not set)");
        }

        private void Send(string command) {
            if (wholeFellow.Checked) command = "/ub bc " + command;
            PluginCore.Command(command);
        }

        public void Dispose() {
            view.Dispose();
        }
    }
}
