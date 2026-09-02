import 'package:shared_preferences/shared_preferences.dart';
import '../models/meter_profile.dart';

class ProfileStore {
  static const _key = 'meter_profiles_v1';

  Future<List<MeterProfile>> loadProfiles() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key) ?? const [];
    return raw.map(MeterProfile.decode).toList();
  }

  Future<void> saveProfiles(List<MeterProfile> profiles) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_key, profiles.map((e) => e.encode()).toList());
  }
}
