// Cible : Web (dart:io interdit).
import 'package:flutter/widgets.dart';

/// Sur Web, un chemin de fichier système n'existe pas : on ne doit jamais
/// arriver ici (les captures sont transmises en `Uint8List`).
ImageProvider createLocalFileImage(String path) => throw UnsupportedError(
      'Les chemins de fichiers locaux ne sont pas supportés sur le Web. '
      'Utilisez Uint8List (XFile.readAsBytes).',
    );
