import 'package:flutter/material.dart';

/// Shared Nagman product colour system, aligned with Nagman People.
abstract final class AppColors {
  static const Color nagmanBlue = Color(0xFF015198);
  static const Color primary = nagmanBlue;
  static const Color nagmanBlueDark = Color(0xFF003B70);
  static const Color nagmanBlueSoft = Color(0xFFE7F2FA);
  static const Color nagmanBluePale = Color(0xFFF3F8FC);
  static const Color skyAccent = Color(0xFF4F9FD1);

  static const Color orange = Color(0xFFFFA900);
  static const Color orangeDeep = Color(0xFF8A5A00);
  static const Color orangeSoft = Color(0xFFFFF1CF);
  static const Color orangePale = Color(0xFFFFF8E8);
  static const Color orangeTint = Color(0xFFFFE3A3);

  static const Color lightBrand = Color(0xFFCCEEFF);
  static const Color blueSoft = Color(0xFFD7ECFA);

  static const Color pageBackground = Color(0xFFF4F7FA);
  static const Color pageTint = Color(0xFFFAFCFE);
  static const Color surface = Colors.white;
  static const Color surfaceSubtle = Color(0xFFF8FAFC);
  static const Color surfaceMuted = Color(0xFFEEF3F7);
  static const Color surfaceStrong = Color(0xFFE3EBF1);

  static const Color ink = Color(0xFF183247);
  static const Color inkStrong = Color(0xFF102431);
  static const Color muted = Color(0xFF566C7D);
  static const Color subtleText = Color(0xFF5F7382);
  static const Color border = Color(0xFFD9E3EA);
  static const Color borderStrong = Color(0xFFB9CAD6);

  static const Color success = Color(0xFF117A30);
  static const Color successSoft = Color(0xFFE0F9E0);
  static const Color warning = orangeDeep;
  static const Color warningSoft = Color(0xFFFFF4DA);
  static const Color danger = Color(0xFFC33A3A);
  static const Color dangerSoft = Color(0xFFFCECEC);
  static const Color info = Color(0xFF3277B8);
  static const Color infoSoft = Color(0xFFEAF2FA);
  static const Color slate = Color(0xFF687784);
  static const Color disabled = Color(0xFF9AA8B2);
  static const Color focus = Color(0xFF0A6AB8);
  static const Color scrim = Color(0x8A102431);
}
