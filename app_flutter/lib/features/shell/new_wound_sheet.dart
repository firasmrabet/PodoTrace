import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../state/app_state.dart';

/// Feuille de création d'une plaie suivie.
class NewWoundSheet extends StatefulWidget {
  const NewWoundSheet({super.key});

  @override
  State<NewWoundSheet> createState() => _NewWoundSheetState();
}

class _NewWoundSheetState extends State<NewWoundSheet> {
  final _label = TextEditingController(text: 'Ulcère plantaire');
  String _site = 'hallux';
  String _side = 'right';
  int _wagner = 1;
  bool _saving = false;

  static const _sites = {
    'hallux': 'Hallux (gros orteil)',
    'plantar_mtp': 'Tête du 1er métatarsien',
    'heel': 'Talon',
    'lateral': 'Bord latéral du pied',
    'dorsum': 'Dos du pied',
    'toes': 'Autres orteils',
    'ankle': 'Cheville',
  };

  @override
  void dispose() {
    _label.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Container(
        decoration: const BoxDecoration(
          color: DfColors.plum,
          borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
          border: Border(top: BorderSide(color: DfColors.hairline)),
        ),
        padding: const EdgeInsets.fromLTRB(22, 14, 22, 26),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 46,
                height: 4,
                decoration: BoxDecoration(
                  color: DfColors.hairline,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text('NOUVELLE PLAIE', style: DfType.overline),
            const SizedBox(height: 8),
            Text('Référencer une lésion', style: DfType.h2),
            const SizedBox(height: 6),
            Text(
              'Ces informations servent au suivi longitudinal et au rapport PDF.',
              style: DfType.caption,
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _label,
              style: DfType.body.copyWith(color: DfColors.cream),
              decoration:
                  const InputDecoration(labelText: 'Libellé de la plaie'),
            ),
            const SizedBox(height: 14),
            DropdownButtonFormField<String>(
              initialValue: _site,
              dropdownColor: DfColors.plumLift,
              decoration:
                  const InputDecoration(labelText: 'Localisation anatomique'),
              items: [
                for (final e in _sites.entries)
                  DropdownMenuItem(value: e.key, child: Text(e.value)),
              ],
              onChanged: (v) => setState(() => _site = v ?? 'hallux'),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _side,
                    dropdownColor: DfColors.plumLift,
                    decoration: const InputDecoration(labelText: 'Pied'),
                    items: const [
                      DropdownMenuItem(value: 'right', child: Text('Droit')),
                      DropdownMenuItem(value: 'left', child: Text('Gauche')),
                    ],
                    onChanged: (v) => setState(() => _side = v ?? 'right'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<int>(
                    initialValue: _wagner,
                    dropdownColor: DfColors.plumLift,
                    decoration:
                        const InputDecoration(labelText: 'Grade Wagner'),
                    items: [
                      for (var i = 0; i <= 5; i++)
                        DropdownMenuItem(value: i, child: Text('$i')),
                    ],
                    onChanged: (v) => setState(() => _wagner = v ?? 1),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            DfPrimaryButton(
              label: 'Enregistrer la plaie',
              icon: Icons.add_rounded,
              expand: true,
              loading: _saving,
              onPressed: _saving
                  ? null
                  : () async {
                      setState(() => _saving = true);
                      final woundProvider = context.read<WoundProvider>();
                      final created = await woundProvider.createWound(
                        label: _label.text.trim().isEmpty
                            ? 'Plaie'
                            : _label.text.trim(),
                        site: _site,
                        side: _side,
                        wagner: _wagner,
                      );
                      if (!context.mounted) return;
                      Navigator.of(context).pop(created != null);
                    },
            ),
          ],
        ),
      ),
    );
  }
}
