import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/meter_profile.dart';
import '../services/profile_store.dart';
import 'profile_wizard.dart';
import 'capture_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _store = ProfileStore();
  List<MeterProfile> _profiles = [];
  String _baseUrl = 'http://192.168.1.10:5000';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final profiles = await _store.loadProfiles();
    if (!mounted) return;
    setState(() {
      _profiles = profiles;
      _baseUrl = prefs.getString('ocr_base_url') ?? _baseUrl;
      _loading = false;
    });
  }

  Future<void> _newProfile() async {
    final profile = await Navigator.push<MeterProfile>(context, MaterialPageRoute(builder: (_) => const ProfileWizard()));
    if (profile == null) return;
    setState(() => _profiles = [..._profiles, profile]);
    await _store.saveProfiles(_profiles);
  }

  Future<void> _configureServer() async {
    final controller = TextEditingController(text: _baseUrl);
    final value = await showDialog<String>(context: context, builder: (context) => AlertDialog(
      title: const Text('OCR Engine'),
      content: TextField(controller: controller, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Server address', hintText: 'http://192.168.1.20:5000', border: OutlineInputBorder())),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Save'))],
    ));
    if (value == null || value.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ocr_base_url', value.replaceAll(RegExp(r'/$'), ''));
    setState(() => _baseUrl = value.replaceAll(RegExp(r'/$'), ''));
  }

  Future<void> _delete(MeterProfile profile) async {
    setState(() => _profiles = _profiles.where((e) => e.id != profile.id).toList());
    await _store.saveProfiles(_profiles);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Nagman Meter Reader', style: TextStyle(fontWeight: FontWeight.w800)), Text('Mechanical Water Meter OCR', style: TextStyle(fontSize: 12, fontWeight: FontWeight.normal))]),
        actions: [IconButton(onPressed: _configureServer, tooltip: 'OCR server', icon: const Icon(Icons.settings_ethernet))],
      ),
      floatingActionButton: FloatingActionButton.extended(onPressed: _newProfile, icon: const Icon(Icons.add), label: const Text('Configure Meter')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _profiles.isEmpty
              ? Center(child: Padding(padding: const EdgeInsets.all(28), child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.water_drop_outlined, size: 76, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 20),
                  const Text('No meter profiles yet', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 8),
                  const Text('Create a visual profile once, position each dial to match the meter, then reuse it whenever you capture a reading.', textAlign: TextAlign.center),
                  const SizedBox(height: 22),
                  FilledButton.icon(onPressed: _newProfile, icon: const Icon(Icons.auto_fix_high), label: const Padding(padding: EdgeInsets.all(12), child: Text('Start Configure Wizard'))),
                ])))
              : ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 100), children: [
                  Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)), child: Row(children: [const Icon(Icons.hub_outlined), const SizedBox(width: 10), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('OCR engine', style: TextStyle(fontSize: 12)), Text(_baseUrl, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700))])), TextButton(onPressed: _configureServer, child: const Text('Change'))])),
                  const SizedBox(height: 18),
                  const Text('Meter Profiles', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 10),
                  ..._profiles.map((profile) => Padding(padding: const EdgeInsets.only(bottom: 12), child: Card(child: InkWell(borderRadius: BorderRadius.circular(18), onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => CaptureScreen(profile: profile, baseUrl: _baseUrl))), child: Padding(padding: const EdgeInsets.all(16), child: Row(children: [
                    Container(width: 62, height: 62, decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(16)), child: const Icon(Icons.speed, size: 34)),
                    const SizedBox(width: 14),
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(profile.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)), const SizedBox(height: 4), Text('${profile.counterDigits} counter digits • ${profile.dials.length} rotary dials • ${profile.baseUnit}'), Text('${profile.layout.name} • ${profile.imageRotation}°', style: TextStyle(color: Colors.blueGrey.shade600, fontSize: 12))])),
                    PopupMenuButton<String>(onSelected: (value) { if (value == 'delete') _delete(profile); }, itemBuilder: (_) => const [PopupMenuItem(value: 'delete', child: Row(children: [Icon(Icons.delete_outline), SizedBox(width: 8), Text('Delete')]))]),
                  ]))))),
                ]),
    );
  }
}
