import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../state/app_state.dart';
import '../analysis/analysis_result_screen.dart';
import '../capture/capture_screen.dart';
import '../chat/chat_screen.dart';
import '../dashboard/dashboard_screen.dart';
import '../history/history_screen.dart';
import '../map/map_screen.dart';
import '../practitioner/practitioner_screen.dart';
import '../settings/settings_screen.dart';
import 'new_wound_sheet.dart';

/// Coque responsive : NavigationBar (mobile) ⇄ NavigationRail (tablette/desktop).
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  static const _destinations = <_Destination>[
    _Destination(
        'Accueil', Icons.space_dashboard_outlined, Icons.space_dashboard),
    _Destination('Historique', Icons.timeline_outlined, Icons.timeline),
    _Destination('Assistant', Icons.auto_awesome_outlined, Icons.auto_awesome),
    _Destination('Centres', Icons.map_outlined, Icons.map),
    _Destination('Profil', Icons.person_outline_rounded, Icons.person),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<WoundProvider>().load();
    });
  }

  List<Widget> get _pages => [
        const DashboardScreen(),
        const HistoryScreen(),
        const ChatScreen(),
        const MapScreen(),
        const SettingsScreen(),
      ];

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final isWide = width >= AppConfig.tabletBreakpoint;
    final user = context.watch<AuthProvider>().user;

    if (user?.isPractitioner == true && _index == 0) {
      // L'espace praticien remplace le tableau de bord patient sur l'onglet 0.
      return _buildFrame(
        isWide: isWide,
        body: const PractitionerScreen(),
        extraNav: null,
      );
    }

    return _buildFrame(
      isWide: isWide,
      body: IndexedStack(index: _index, children: _pages),
      extraNav: null,
    );
  }

  Widget _buildFrame({
    required bool isWide,
    required Widget body,
    required Widget? extraNav,
  }) {
    return Scaffold(
      extendBody: true,
      body: DfScaffoldBackground(
        child: SafeArea(
          bottom: false,
          child: Row(
            children: [
              if (isWide)
                _Rail(
                  index: _index,
                  destinations: _destinations,
                  onSelect: (i) => setState(() => _index = i),
                ),
              Expanded(
                child: Column(
                  children: [
                    _TopBar(title: _destinations[_index].label),
                    Expanded(child: body),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: isWide ? _newAnalysisFab() : null,
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      bottomNavigationBar: isWide
          ? null
          : Container(
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: DfColors.hairline)),
              ),
              child: NavigationBar(
                selectedIndex: _index,
                onDestinationSelected: (i) => setState(() => _index = i),
                destinations: [
                  for (final d in _destinations)
                    NavigationDestination(
                      icon: Icon(d.icon),
                      selectedIcon: Icon(d.activeIcon, color: DfColors.copper),
                      label: d.label,
                    ),
                ],
              ),
            ),
    );
  }

  Widget _newAnalysisFab() {
    return GestureDetector(
      onTap: () => _startAnalysis(context),
      child: Container(
        height: 54,
        padding: const EdgeInsets.symmetric(horizontal: 22),
        decoration: BoxDecoration(
          gradient: DfGradients.copperSheen,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: DfColors.copper.withValues(alpha: 0.35),
              blurRadius: 26,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.add_a_photo_outlined,
                size: 18, color: DfColors.ink),
            const SizedBox(width: 10),
            Text('Nouvelle analyse',
                style: DfType.bodyStrong
                    .copyWith(color: DfColors.ink, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  static Future<void> _startAnalysis(BuildContext context) async {
    final wounds = context.read<WoundProvider>();
    if (wounds.wounds.isEmpty) {
      final created = await showModalBottomSheet<bool>(
        context: context,
        backgroundColor: Colors.transparent,
        isScrollControlled: true,
        builder: (_) => const NewWoundSheet(),
      );
      if (created != true) return;
    }
    if (!context.mounted) return;
    final result = await Navigator.of(context).push<AnalysisLaunchResult>(
      MaterialPageRoute(builder: (_) => const CaptureScreen()),
    );
    if (result != null && context.mounted) {
      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => AnalysisResultScreen(result: result)),
      );
    }
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final locale = context.watch<LocaleProvider>();
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 16, 4),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('DIAFOOT SENTINEL',
                  style: DfType.overline.copyWith(fontSize: 8.5)),
              const SizedBox(height: 3),
              Text(title, style: DfType.h3.copyWith(fontSize: 16)),
            ],
          ),
          const Spacer(),
          IconButton(
            tooltip:
                locale.isFrench ? 'Switch to English' : 'Passer en français',
            onPressed: locale.toggle,
            icon: Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: DfColors.hairline),
              ),
              child: Text(
                locale.isFrench ? 'FR' : 'EN',
                style: DfType.caption.copyWith(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: DfColors.champagne,
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: DfGradients.copperSheen,
                boxShadow: [
                  BoxShadow(
                    color: DfColors.copper.withValues(alpha: 0.28),
                    blurRadius: 16,
                  ),
                ],
              ),
              child: Center(
                child: Text(
                  auth.user?.initials ?? 'DF',
                  style: DfType.caption.copyWith(
                    color: DfColors.ink,
                    fontWeight: FontWeight.w700,
                    fontSize: 11,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Rail extends StatelessWidget {
  const _Rail({
    required this.index,
    required this.destinations,
    required this.onSelect,
  });

  final int index;
  final List<_Destination> destinations;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 92,
      decoration: const BoxDecoration(
        border: Border(right: BorderSide(color: DfColors.hairline)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 22),
          Container(
            width: 40,
            height: 40,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: DfGradients.copperSheen,
            ),
            child: Center(
              child: Text('DF',
                  style: DfType.caption.copyWith(
                      color: DfColors.ink,
                      fontWeight: FontWeight.w800,
                      fontSize: 12)),
            ),
          ),
          const SizedBox(height: 20),
          Expanded(
            child: NavigationRail(
              selectedIndex: index,
              onDestinationSelected: onSelect,
              labelType: NavigationRailLabelType.all,
              backgroundColor: Colors.transparent,
              destinations: [
                for (final d in destinations)
                  NavigationRailDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.activeIcon, color: DfColors.copper),
                    label: Text(d.label),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Destination {
  const _Destination(this.label, this.icon, this.activeIcon);

  final String label;
  final IconData icon;
  final IconData activeIcon;
}
