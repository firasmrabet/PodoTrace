import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/models/models.dart';
import '../../data/services/api_service.dart';
import '../../state/app_state.dart';

/// Assistant médical IA (RAG IWGDF) avec détection d'urgence immédiate.
class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    this.embedded = true,
    this.woundId,
    this.contextLabel,
  });

  final bool embedded;
  final int? woundId;
  final String? contextLabel;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<ChatEntry> _messages = [];
  List<String> _suggestions = const [];
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _messages.add(ChatEntry(
      text: 'Bonjour. Je suis l\'assistant PodoTrace, adossé aux '
          'recommandations internationales IWGDF. Vous pouvez me décrire '
          'l\'aspect de votre plaie ou poser une question sur votre suivi.\n\n'
          'Je ne pose pas de diagnostic et ne remplace pas votre médecin.',
      isUser: false,
    ));
    _loadSuggestions();
  }

  Future<void> _loadSuggestions() async {
    final api = context.read<ApiService>();
    final locale = context.read<LocaleProvider>().locale;
    final s = await api.chatSuggestions(locale: locale);
    if (mounted) setState(() => _suggestions = s);
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _messages.add(ChatEntry(text: text, isUser: true));
      _messages.add(ChatEntry(text: '', isUser: false, pending: true));
      _sending = true;
      _input.clear();
    });
    _scrollToEnd();

    try {
      final reply = await context.read<ApiService>().chat(
            message: text,
            woundId: widget.woundId,
            locale: context.read<LocaleProvider>().locale,
          );
      if (!mounted) return;
      setState(() {
        _messages.removeWhere((m) => m.pending);
        _messages.add(ChatEntry(
          text: reply.reply,
          isUser: false,
          redFlag: reply.redFlag,
          sources: reply.sources,
        ));
        _sending = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.removeWhere((m) => m.pending);
        _messages.add(ChatEntry(
          text: 'Connexion interrompue : ${e.message}\n\n'
              'En cas de doute sur votre plaie, contactez votre praticien référent. '
              'En cas de fièvre, douleur brutale ou extension rapide de la rougeur, '
              'appelez le 15 / 190.',
          isUser: false,
        ));
        _sending = false;
      });
    }
    _scrollToEnd();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent + 120,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(
      children: [
        if (widget.contextLabel != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
            child: Row(
              children: [
                const Icon(Icons.attach_file_rounded,
                    size: 13, color: DfColors.copper),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    'Contexte injecté : ${widget.contextLabel}',
                    style: DfType.caption.copyWith(fontSize: 10),
                  ),
                ),
              ],
            ),
          ),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            itemCount: _messages.length,
            itemBuilder: (context, i) => _bubble(_messages[i]),
          ),
        ),
        if (_suggestions.isNotEmpty && _messages.length <= 1)
          SizedBox(
            height: 40,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _suggestions.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, i) => GestureDetector(
                onTap: () => _send(_suggestions[i]),
                child: Container(
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: DfColors.hairline),
                    color: DfColors.plumSoft,
                  ),
                  child: Text(_suggestions[i],
                      style: DfType.caption.copyWith(fontSize: 10.5)),
                ),
              ),
            ),
          ),
        _composer(),
      ],
    );

    if (widget.embedded) {
      return DfContentFrame(
          maxWidth: 760, padding: EdgeInsets.zero, child: content);
    }
    return Scaffold(
      body: DfScaffoldBackground(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 6, 16, 2),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: DfColors.creamDim),
                    ),
                    Text('Assistant PodoTrace',
                        style: DfType.h3.copyWith(fontSize: 16)),
                  ],
                ),
              ),
              Expanded(child: content),
            ],
          ),
        ),
      ),
    );
  }

  Widget _bubble(ChatEntry message) {
    if (message.pending) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 14, right: 40),
        child: DfGlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 13,
                height: 13,
                child: CircularProgressIndicator(strokeWidth: 1.6),
              ),
              const SizedBox(width: 12),
              Text('Consultation des recommandations IWGDF…',
                  style: DfType.caption.copyWith(fontSize: 10.5)),
            ],
          ),
        ),
      );
    }

    final isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width *
              (widget.embedded ? 0.78 : 0.82),
        ),
        margin: EdgeInsets.only(
          bottom: 14,
          left: isUser ? 44 : 0,
          right: isUser ? 0 : 44,
        ),
        child: Column(
          crossAxisAlignment:
              isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            if (message.redFlag)
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding:
                    const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
                decoration: BoxDecoration(
                  color: DfColors.critical.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: DfColors.critical.withValues(alpha: 0.55)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.emergency_outlined,
                        size: 16, color: DfColors.critical),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'URGENCE POTENTIELLE — Appelez le 15 / 190 ou rendez-vous '
                        'aux urgences les plus proches sans attendre.',
                        style: DfType.caption.copyWith(
                          color: DfColors.critical,
                          fontWeight: FontWeight.w600,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            DfGlassCard(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              accent: message.redFlag
                  ? DfColors.critical
                  : (isUser ? DfColors.copper : null),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    message.text,
                    style: DfType.body.copyWith(
                      fontSize: 13,
                      height: 1.65,
                      color: isUser ? DfColors.champagne : DfColors.creamDim,
                    ),
                  ),
                  if (message.sources.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final s in message.sources)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 9, vertical: 4),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: DfColors.hairline),
                            ),
                            child: Text(s,
                                style: DfType.caption.copyWith(fontSize: 9)),
                          ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _composer() {
    return Container(
      padding: EdgeInsets.fromLTRB(
        16,
        10,
        16,
        10 + MediaQuery.viewInsetsOf(context).bottom * 0.0,
      ),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: DfColors.hairline)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _input,
              minLines: 1,
              maxLines: 4,
              style: DfType.body.copyWith(color: DfColors.cream, fontSize: 13),
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _send(),
              decoration: InputDecoration(
                hintText: 'Décrivez votre plaie ou posez une question…',
                hintStyle: DfType.caption.copyWith(fontSize: 11.5),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
                suffixIcon: _sending
                    ? const Padding(
                        padding: EdgeInsets.all(13),
                        child: SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 1.6),
                        ),
                      )
                    : IconButton(
                        onPressed: _send,
                        icon: const Icon(Icons.send_rounded,
                            size: 17, color: DfColors.copper),
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
