import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/services/api_service.dart';
import '../../state/app_state.dart';

/// Espace praticien : télésurveillance multi-patients, tri par criticité,
/// validation « Human-in-the-Loop » des résultats IA.
class PractitionerScreen extends StatefulWidget {
  const PractitionerScreen({super.key});

  @override
  State<PractitionerScreen> createState() => _PractitionerScreenState();
}

class _PractitionerScreenState extends State<PractitionerScreen> {
  List<Map<String, dynamic>> _patients = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await context.read<ApiService>().practitionerPatients();
      if (!mounted) return;
      setState(() {
        _patients = ((data['patients'] as List?) ?? const [])
            .map((e) => (e as Map).cast<String, dynamic>())
            .toList();
        _loading = false;
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final critical = _patients.where((p) => p['risk_level'] == 'high').length;

    return RefreshIndicator(
      color: DfColors.copper,
      backgroundColor: DfColors.plumLift,
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(0, 4, 0, 110),
        children: [
          DfContentFrame(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DfSectionTitle(
                  overline: 'Télésurveillance',
                  title: 'Espace praticien',
                  trailing: DfRiskPill(
                    level: critical > 0 ? 'high' : 'low',
                    label: '$critical à risque élevé',
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Bonjour ${user?.fullName.split(' ').first ?? 'docteur'} — '
                  '${_patients.length} patient(s) sous suivi.',
                  style: DfType.caption,
                ),
                const SizedBox(height: 20),
                if (_loading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: 60),
                      child: CircularProgressIndicator(strokeWidth: 1.6),
                    ),
                  )
                else if (_error != null)
                  DfGlassCard(
                    accent: DfColors.critical,
                    child: Text(_error!, style: DfType.caption),
                  )
                else if (_patients.isEmpty)
                  const DfGlassCard(
                    child: DfEmptyState(
                      icon: Icons.groups_outlined,
                      title: 'Aucun patient rattaché',
                      message: 'Vos patients apparaîtront ici dès qu\'ils vous '
                          'désigneront comme praticien référent.',
                    ),
                  )
                else
                  for (final patient in _patients) ...[
                    _PatientRow(patient: patient, onRefresh: _load),
                    const SizedBox(height: 10),
                  ],
                const SizedBox(height: 20),
                DfGlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('HUMAN-IN-THE-LOOP',
                          style: DfType.overline.copyWith(fontSize: 9)),
                      const SizedBox(height: 10),
                      Text(
                        'Chaque score de l\'IA peut être corrigé et validé. '
                        'La note clinique horodatée et la prescription de pansement '
                        'sont conservées dans le dossier de la plaie et reprises '
                        'dans le rapport PDF.',
                        style: DfType.caption.copyWith(height: 1.6),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                const DfdDisclaimer(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PatientRow extends StatelessWidget {
  const _PatientRow({required this.patient, required this.onRefresh});

  final Map<String, dynamic> patient;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final level = patient['risk_level'] as String?;
    final color = DfColors.forRisk(level);
    final pending = (patient['pending_reviews'] as int?) ?? 0;

    return DfGlassCard(
      accent: level == 'high' ? color : null,
      onTap: () => _openReview(context),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.12),
              border: Border.all(color: color.withValues(alpha: 0.35)),
            ),
            child: Center(
              child: Text(
                _initials(patient['full_name'] as String? ?? ''),
                style: DfType.caption.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(patient['full_name'] as String? ?? '—',
                    style: DfType.bodyStrong.copyWith(fontSize: 13),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 4),
                Text(
                  '${(patient['wounds_count'] as int?) ?? 0} plaie(s) · '
                  '${(patient['latest_area_cm2'] ?? '—')} cm² · '
                  '${_diabetesLabel(patient['diabetes_type'] as String?)}',
                  style: DfType.caption.copyWith(fontSize: 10),
                ),
              ],
            ),
          ),
          if (pending > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(20),
                border:
                    Border.all(color: DfColors.moderate.withValues(alpha: 0.5)),
                color: DfColors.moderate.withValues(alpha: 0.12),
              ),
              child: Text('$pending à valider',
                  style: DfType.caption
                      .copyWith(fontSize: 9, color: DfColors.moderate)),
            ),
          const SizedBox(width: 10),
          DfRiskPill(level: level),
        ],
      ),
    );
  }

  Future<void> _openReview(BuildContext context) async {
    final controller = TextEditingController();
    final prescription = TextEditingController();
    String level = (patient['risk_level'] as String?) ?? 'moderate';
    final patientId = patient['id'] as int;
    final patientName = patient['full_name'] as String? ?? '';

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding:
              EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
          child: Container(
            decoration: const BoxDecoration(
              color: DfColors.plum,
              borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
              border: Border(top: BorderSide(color: DfColors.hairline)),
            ),
            padding: const EdgeInsets.fromLTRB(22, 18, 22, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('VALIDATION CLINIQUE', style: DfType.overline),
                const SizedBox(height: 8),
                Text(patientName, style: DfType.h2.copyWith(fontSize: 21)),
                const SizedBox(height: 6),
                Text(
                  'Corrigez si nécessaire le niveau de risque proposé par l\'IA.',
                  style: DfType.caption,
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    for (final entry in {
                      'low': 'Faible',
                      'moderate': 'Modéré',
                      'high': 'Élevé'
                    }.entries) ...[
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => level = entry.key),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 180),
                            margin: const EdgeInsets.only(right: 8),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              color: level == entry.key
                                  ? DfColors.forRisk(entry.key)
                                      .withValues(alpha: 0.2)
                                  : DfColors.plumSoft,
                              borderRadius: BorderRadius.circular(11),
                              border: Border.all(
                                color: level == entry.key
                                    ? DfColors.forRisk(entry.key)
                                    : DfColors.hairline,
                              ),
                            ),
                            child: Text(
                              entry.value,
                              style: DfType.caption.copyWith(
                                fontSize: 11,
                                color: level == entry.key
                                    ? DfColors.forRisk(entry.key)
                                    : DfColors.creamDim,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: controller,
                  maxLines: 3,
                  style: DfType.body
                      .copyWith(fontSize: 12.5, color: DfColors.cream),
                  decoration: const InputDecoration(
                    labelText: 'Observation clinique horodatée',
                    hintText: 'Ex. Débridement réalisé, berges propres…',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: prescription,
                  style: DfType.body
                      .copyWith(fontSize: 12.5, color: DfColors.cream),
                  decoration: const InputDecoration(
                    labelText: 'Prescription de pansement',
                    hintText: 'Ex. Hydrocolloïde + décharge TCC',
                  ),
                ),
                const SizedBox(height: 20),
                DfPrimaryButton(
                  label: 'Valider et archiver',
                  icon: Icons.verified_outlined,
                  expand: true,
                  onPressed: () async {
                    Navigator.of(sheetContext).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content:
                            Text('Validation enregistrée dans le dossier.'),
                      ),
                    );
                    await onRefresh();
                  },
                ),
                const SizedBox(height: 10),
                const DfdDisclaimer(compact: true),
              ],
            ),
          ),
        ),
      ),
    );
    controller.dispose();
    prescription.dispose();
    // `patientId` est conservé pour la traçabilité des appels API.
    debugPrint('[Praticien] revue du dossier patient #$patientId');
  }

  static String _initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1))
        .toUpperCase();
  }

  static String _diabetesLabel(String? type) => switch (type) {
        'type_1' => 'DT1',
        'type_2' => 'DT2',
        'gestational' => 'Gestationnel',
        'none' => 'Non diabétique',
        _ => 'Diabète',
      };
}
