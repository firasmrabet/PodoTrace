import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/services/api_service.dart';
import '../../state/app_state.dart';

/// Profil, préférences, biométrie, conformité.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _biometricBusy = false;

  bool get biometricBusy => _biometricBusy;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user;
    final locale = context.watch<LocaleProvider>();

    return Scaffold(
      body: DfScaffoldBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(0, 4, 0, 40),
            children: [
              DfContentFrame(
                maxWidth: 640,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        if (Navigator.of(context).canPop())
                          IconButton(
                            onPressed: () => Navigator.of(context).pop(),
                            icon: const Icon(Icons.arrow_back_rounded,
                                color: DfColors.creamDim),
                          ),
                        Expanded(
                          child: Text('Profil & réglages',
                              style: DfType.h2.copyWith(fontSize: 21)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),

                    // --- Identité -------------------------------------
                    DfGlassCard(
                      accent: DfColors.copper,
                      child: Row(
                        children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: const BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: DfGradients.copperSheen,
                            ),
                            child: Center(
                              child: Text(
                                user?.initials ?? 'DF',
                                style: DfType.h3.copyWith(
                                    color: DfColors.ink, fontSize: 18),
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(user?.fullName ?? '—',
                                    style: DfType.bodyStrong
                                        .copyWith(fontSize: 14)),
                                const SizedBox(height: 4),
                                Text(user?.email ?? '',
                                    style:
                                        DfType.caption.copyWith(fontSize: 11)),
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    DfRiskPill(
                                      level: 'low',
                                      label: user?.isPractitioner == true
                                          ? 'Praticien'
                                          : 'Patient',
                                    ),
                                    const SizedBox(width: 8),
                                    if (user?.emailVerified == true)
                                      const DfRiskPill(
                                          level: 'low', label: 'Email vérifié'),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),

                    Text('PROFIL CLINIQUE',
                        style: DfType.overline.copyWith(fontSize: 9)),
                    const SizedBox(height: 10),
                    DfGlassCard(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 18, vertical: 8),
                      child: Column(
                        children: [
                          _switchRow(
                            'Neuropathie sensitive',
                            'Perte de sensibilité protective du pied',
                            user?.neuropathy ?? false,
                            (v) => _patch({'neuropathy': v}),
                          ),
                          const Divider(height: 1),
                          _switchRow(
                            'Artériopathie (AOMI)',
                            'Antécédent d\'artériopathie oblitérante',
                            user?.peripheralArteryDisease ?? false,
                            (v) => _patch({'peripheral_artery_disease': v}),
                          ),
                          const Divider(height: 1),
                          _switchRow(
                            'Déverrouillage biométrique',
                            kIsWeb
                                ? 'Indisponible sur navigateur'
                                : 'Face ID / empreinte digitale',
                            user?.biometricEnabled ?? false,
                            (v) => _toggleBiometrics(v),
                            enabled: !kIsWeb,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),

                    Text('PRÉFÉRENCES',
                        style: DfType.overline.copyWith(fontSize: 9)),
                    const SizedBox(height: 10),
                    DfGlassCard(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 18, vertical: 8),
                      child: Column(
                        children: [
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text('Langue de l\'interface',
                                style: DfType.body.copyWith(fontSize: 12.5)),
                            subtitle: Text(
                              locale.isFrench ? 'Français' : 'English',
                              style: DfType.caption.copyWith(fontSize: 10.5),
                            ),
                            trailing: DfGhostButton(
                              label: locale.isFrench ? 'EN' : 'FR',
                              onPressed: locale.toggle,
                            ),
                          ),
                          const Divider(height: 1),
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text('Serveur API',
                                style: DfType.body.copyWith(fontSize: 12.5)),
                            subtitle: Text(AppConfig.apiBase,
                                style: DfType.caption.copyWith(fontSize: 10)),
                            trailing: const Icon(Icons.dns_outlined,
                                size: 17, color: DfColors.muted),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),

                    Text('CONFORMITÉ & DONNÉES',
                        style: DfType.overline.copyWith(fontSize: 9)),
                    const SizedBox(height: 10),
                    DfGlassCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _infoRow(Icons.lock_outline_rounded,
                              'Chiffrement au repos (AES) des images médicales'),
                          _infoRow(Icons.badge_outlined,
                              'Outil d\'aide en phase de validation clinique'),
                          _infoRow(Icons.privacy_tip_outlined,
                              'Accès strictement contrôlé par jeton JWT'),
                          _infoRow(Icons.history_rounded,
                              'Journal d\'audit horodaté des accès (HDS)'),
                          if (auth.isDegradedStorage)
                            _infoRow(
                              Icons.warning_amber_rounded,
                              'Stockage sécurisé dégradé sur ce navigateur',
                              color: DfColors.moderate,
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    DfGhostButton(
                      label: 'Se déconnecter',
                      icon: Icons.logout_rounded,
                      danger: true,
                      onPressed: () async {
                        await context.read<AuthProvider>().logout();
                        if (context.mounted) Navigator.of(context).pop();
                      },
                    ),
                    const SizedBox(height: 20),
                    Text(
                      '${AppConfig.appName} v${AppConfig.version} · build ${kReleaseMode ? 'release' : 'debug'}',
                      style: DfType.caption.copyWith(fontSize: 9.5),
                    ),
                    const SizedBox(height: 10),
                    const DfdDisclaimer(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _switchRow(
    String title,
    String subtitle,
    bool value,
    ValueChanged<bool> onChanged, {
    bool enabled = true,
  }) {
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      value: value,
      onChanged: enabled ? onChanged : null,
      activeThumbColor: DfColors.copper,
      title: Text(title, style: DfType.body.copyWith(fontSize: 12.5)),
      subtitle: Text(subtitle, style: DfType.caption.copyWith(fontSize: 10)),
    );
  }

  Widget _infoRow(IconData icon, String text, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon,
              size: 14, color: color ?? DfColors.copper.withValues(alpha: 0.8)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text,
                style: DfType.caption.copyWith(fontSize: 10.5, height: 1.5)),
          ),
        ],
      ),
    );
  }

  Future<void> _patch(Map<String, dynamic> data) async {
    final auth = context.read<AuthProvider>();
    try {
      await context.read<ApiService>().updateProfile(data);
      await auth.refreshUser();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  Future<void> _toggleBiometrics(bool value) async {
    if (kIsWeb) return;
    setState(() => _biometricBusy = true);
    try {
      final localAuth = LocalAuthentication();
      if (value) {
        final ok = await localAuth.authenticate(
          localizedReason:
              'Activez la biométrie pour déverrouiller PodoTrace',
        );
        if (!ok) return;
      }
      await _patch({'biometric_enabled': value});
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Biométrie indisponible : $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _biometricBusy = false);
    }
  }
}
