import 'dart:convert';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../theme/df_theme.dart';
import 'local_image_binding.dart';

/// Abstraction universelle d'affichage d'image (Mobile · Web · Desktop).
///
/// ⚠️ Règle d'or : **aucun import `dart:io` dans l'UI ni dans un service
/// partagé**. Une image circule sous l'une de ces formes :
///   · `Uint8List`      → octets en mémoire (capture caméra, upload Web, API)
///   · `String` http(s) → URL distante mise en cache
///   · `data:image/...` → data-URI base64 renvoyée par le backend
///   · `String` chemin  → chemin local mobile uniquement, résolu par
///                        `local_image_binding.dart` (import conditionnel).
Widget buildWoundImage(
  Object? imageSource, {
  BoxFit fit = BoxFit.cover,
  double? width,
  double? height,
  Widget? placeholder,
  BorderRadius? borderRadius,
  ColorFilter? colorFilter,
}) {
  Widget child;

  if (imageSource is Uint8List) {
    child = Image.memory(
      imageSource,
      fit: fit,
      width: width,
      height: height,
      gaplessPlayback: true,
      errorBuilder: (_, __, ___) => const DfImageFallback(),
    );
  } else if (imageSource is String && imageSource.startsWith('data:image')) {
    final bytes = decodeDataUri(imageSource);
    child = bytes == null
        ? const DfImageFallback()
        : Image.memory(bytes, fit: fit, width: width, height: height);
  } else if (imageSource is String && imageSource.startsWith('http')) {
    child = CachedNetworkImage(
      imageUrl: imageSource,
      fit: fit,
      width: width,
      height: height,
      placeholder: (_, __) => placeholder ?? const DfImageSkeleton(),
      errorWidget: (_, __, ___) => const DfImageFallback(),
    );
  } else if (imageSource is String && imageSource.isNotEmpty && !kIsWeb) {
    child = Image(
      image: createLocalFileImage(imageSource),
      fit: fit,
      width: width,
      height: height,
      errorBuilder: (_, __, ___) => const DfImageFallback(),
    );
  } else {
    child = placeholder ?? const DfImageFallback();
  }

  if (colorFilter != null && child is Image) {
    child = ColorFiltered(colorFilter: colorFilter, child: child);
  }
  if (borderRadius != null) {
    child = ClipRRect(borderRadius: borderRadius, child: child);
  }
  return child;
}

/// Décode une data-URI `data:image/jpeg;base64,...` (réponse backend).
Uint8List? decodeDataUri(String uri) {
  try {
    final commaIndex = uri.indexOf(',');
    if (commaIndex < 0) return null;
    return base64Decode(uri.substring(commaIndex + 1));
  } catch (_) {
    return null;
  }
}

/// Convertit une réponse base64 nue ou data-URI en octets affichables.
Uint8List? toBytes(Object? payload) {
  if (payload is Uint8List) return payload;
  if (payload is String) {
    if (payload.startsWith('data:image')) return decodeDataUri(payload);
    try {
      return base64Decode(payload);
    } catch (_) {
      return null;
    }
  }
  return null;
}

class DfImageFallback extends StatelessWidget {
  const DfImageFallback({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: DfColors.plumSoft,
      alignment: Alignment.center,
      child: const Icon(
        Icons.image_not_supported_outlined,
        color: DfColors.muted,
        size: 26,
      ),
    );
  }
}

class DfImageSkeleton extends StatelessWidget {
  const DfImageSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(color: DfColors.plumSoft.withValues(alpha: 0.6));
  }
}
