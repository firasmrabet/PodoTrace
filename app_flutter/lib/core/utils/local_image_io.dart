// Cible : mobile & desktop (dart:io disponible).
import 'dart:io';

import 'package:flutter/widgets.dart';

/// Fabrique d'ImageProvider pour un fichier local.
ImageProvider createLocalFileImage(String path) => FileImage(File(path));
