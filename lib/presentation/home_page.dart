import 'package:flutter/material.dart';

import '../data/operations_store.dart';
import '../domain/dispatch_rules.dart';
import '../domain/models.dart';

const _ink = Color(0xFF18212F);
const _muted = Color(0xFF6D7785);
const _line = Color(0xFFE5E8ED);

Color priorityColor(Priority p) => switch (p) {
  Priority.critical => const Color(0xFFB42318),
  Priority.high => const Color(0xFFD65A31),
  Priority.medium => const Color(0xFFAD7411),
  Priority.low => const Color(0xFF327A5B),
};
Color statusColor(String s) =>
    s.toLowerCase().contains('available') || s == 'Resolved'
    ? const Color(0xFF327A5B)
    : s.toLowerCase().contains('off')
    ? const Color(0xFF6D7785)
    : const Color(0xFF3569A8);

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.store});
  final OperationsStore store;
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int index = 0;
  final titles = [
    'Operations overview',
    'Incident queue',
    'Response teams',
    'Resource board',
    'Activity & reports',
  ];
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.store,
    builder: (context, _) => Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFFF6F7F9),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              titles[index],
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 19,
                color: _ink,
              ),
            ),
            const Text(
              'SIMULATED OPERATIONS • TRAINING PROTOTYPE',
              style: TextStyle(
                fontSize: 9,
                letterSpacing: 1.05,
                color: _muted,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Open workspace',
            icon: const Icon(Icons.account_circle_outlined),
            onSelected: (v) {
              if (v == 'responder') {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ResponderWorkspace(store: widget.store),
                  ),
                );
              } else {
                setState(() => index = 0);
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: 'coordinator',
                child: Text('Coordinator console'),
              ),
              PopupMenuItem(
                value: 'responder',
                child: Text('Responder workspace'),
              ),
            ],
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: index,
          children: [
            OverviewPage(
              store: widget.store,
              onOpenIncident: (i) => openIncident(context, widget.store, i),
            ),
            IncidentsPage(
              store: widget.store,
              onOpen: (i) => openIncident(context, widget.store, i),
            ),
            RespondersPage(store: widget.store),
            ResourcesPage(store: widget.store),
            ReportsPage(store: widget.store),
          ],
        ),
      ),
      floatingActionButton: index == 1
          ? FloatingActionButton.extended(
              onPressed: () => showCreateIncident(context, widget.store),
              icon: const Icon(Icons.add),
              label: const Text('New incident'),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (v) => setState(() => index = v),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.grid_view_outlined),
            selectedIcon: Icon(Icons.grid_view_rounded),
            label: 'Overview',
          ),
          NavigationDestination(
            icon: Icon(Icons.warning_amber_rounded),
            label: 'Incidents',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_outlined),
            label: 'Responders',
          ),
          NavigationDestination(
            icon: Icon(Icons.inventory_2_outlined),
            label: 'Resources',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_rounded),
            label: 'Reports',
          ),
        ],
      ),
    ),
  );
}

class PagePad extends StatelessWidget {
  const PagePad({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 820),
      child: child,
    ),
  );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.title, {super.key, this.trailing});
  final String title;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 18, bottom: 10),
    child: Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w700, color: _ink),
          ),
        ),
        ?trailing,
      ],
    ),
  );
}

class Panel extends StatelessWidget {
  const Panel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => Card(
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: _line),
    ),
    child: Padding(padding: padding, child: child),
  );
}

class OverviewPage extends StatelessWidget {
  const OverviewPage({
    super.key,
    required this.store,
    required this.onOpenIncident,
  });
  final OperationsStore store;
  final ValueChanged<Incident> onOpenIncident;
  @override
  Widget build(BuildContext context) {
    final active = store.activeIncidents;
    final critical = active
        .where((i) => i.priority == Priority.critical)
        .length;
    final available = store.responders
        .where((r) => r.status == ResponderStatus.available)
        .length;
    final assigned = active.where((i) => i.responderId != null).length;
    return PagePad(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (store.storageError != null)
            StorageWarning(text: store.storageError!),
          const Panel(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, color: Color(0xFF3569A8)),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Training workspace. Sample records are simulated; this app does not contact emergency services or share live location.',
                    style: TextStyle(
                      color: _ink,
                      height: 1.4,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, c) => Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                MetricCard(
                  label: 'Active incidents',
                  value: '${active.length}',
                  icon: Icons.warning_amber_rounded,
                  accent: const Color(0xFFB64032),
                  width: (c.maxWidth - 20) / 3,
                ),
                MetricCard(
                  label: 'Critical',
                  value: '$critical',
                  icon: Icons.priority_high,
                  accent: priorityColor(Priority.critical),
                  width: (c.maxWidth - 20) / 3,
                ),
                MetricCard(
                  label: 'Teams ready',
                  value: '$available',
                  icon: Icons.groups_outlined,
                  accent: const Color(0xFF327A5B),
                  width: (c.maxWidth - 20) / 3,
                ),
              ],
            ),
          ),
          SectionTitle(
            'Priority queue',
            trailing: Text(
              '${active.length} OPEN',
              style: const TextStyle(
                fontSize: 10,
                letterSpacing: .8,
                color: _muted,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          if (active.isEmpty)
            const EmptyPanel(
              icon: Icons.check_circle_outline,
              title: 'No active incidents',
              detail: 'New requests will appear here for review.',
            )
          else
            ...active
                .take(4)
                .map(
                  (i) => Padding(
                    padding: const EdgeInsets.only(bottom: 9),
                    child: IncidentTile(
                      incident: i,
                      store: store,
                      onTap: () => onOpenIncident(i),
                    ),
                  ),
                ),
          SectionTitle(
            'Team readiness',
            trailing: Text(
              '$assigned DEPLOYED',
              style: const TextStyle(
                fontSize: 10,
                letterSpacing: .8,
                color: _muted,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Panel(
            child: Column(
              children: store.responders
                  .take(4)
                  .map(
                    (r) =>
                        ResponderRow(responder: r, store: store, compact: true),
                  )
                  .toList(),
            ),
          ),
          if (store.events.isNotEmpty) ...[
            const SectionTitle('Recent activity'),
            Panel(
              child: Column(
                children: store.events
                    .take(3)
                    .map((e) => ActivityRow(event: e))
                    .toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    required this.accent,
    required this.width,
  });
  final String label, value;
  final IconData icon;
  final Color accent;
  final double width;
  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    child: Panel(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: accent, size: 20),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 25,
              fontWeight: FontWeight.w800,
              color: _ink,
            ),
          ),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11, color: _muted),
          ),
        ],
      ),
    ),
  );
}

class IncidentsPage extends StatefulWidget {
  const IncidentsPage({super.key, required this.store, required this.onOpen});
  final OperationsStore store;
  final ValueChanged<Incident> onOpen;
  @override
  State<IncidentsPage> createState() => _IncidentsPageState();
}

class _IncidentsPageState extends State<IncidentsPage> {
  String filter = 'All';
  String query = '';
  @override
  Widget build(BuildContext context) {
    final all = [...widget.store.activeIncidents, ...widget.store.history];
    final filtered = all
        .where(
          (i) =>
              (filter == 'All' ||
                  (filter == 'Active' ? i.active : !i.active)) &&
              (query.isEmpty ||
                  '${i.type} ${i.location} ${i.description}'
                      .toLowerCase()
                      .contains(query.toLowerCase())),
        )
        .toList();
    return PagePad(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.store.storageError != null)
            StorageWarning(text: widget.store.storageError!),
          TextField(
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Search incidents by type or location',
              isDense: true,
            ),
            onChanged: (v) => setState(() => query = v),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            children: ['All', 'Active', 'Resolved']
                .map(
                  (v) => ChoiceChip(
                    label: Text(v),
                    selected: filter == v,
                    onSelected: (_) => setState(() => filter = v),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 12),
          if (filtered.isEmpty)
            const EmptyPanel(
              icon: Icons.inbox_outlined,
              title: 'No matching incidents',
              detail: 'Adjust your search or register a new simulated request.',
            )
          else
            ...filtered.map(
              (i) => Padding(
                padding: const EdgeInsets.only(bottom: 9),
                child: IncidentTile(
                  incident: i,
                  store: widget.store,
                  onTap: () => widget.onOpen(i),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class IncidentTile extends StatelessWidget {
  const IncidentTile({
    super.key,
    required this.incident,
    required this.store,
    required this.onTap,
  });
  final Incident incident;
  final OperationsStore store;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final responder = store.responders
        .where((r) => r.id == incident.responderId)
        .firstOrNull;
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(15),
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: _line),
            borderRadius: BorderRadius.circular(15),
          ),
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  PriorityPill(priority: incident.priority),
                  const Spacer(),
                  Text(
                    incidentStatusName(incident.status).toUpperCase(),
                    style: TextStyle(
                      color: statusColor(incidentStatusName(incident.status)),
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      letterSpacing: .5,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 9),
              Text(
                incident.type,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: _ink,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                incident.location,
                style: const TextStyle(color: _muted, fontSize: 13),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(
                    Icons.person_outline,
                    size: 15,
                    color: responder == null ? _muted : const Color(0xFF3569A8),
                  ),
                  const SizedBox(width: 5),
                  Expanded(
                    child: Text(
                      responder?.name ?? 'Awaiting responder',
                      style: const TextStyle(fontSize: 12, color: _muted),
                    ),
                  ),
                  Text(
                    '${incident.createdAt.hour.toString().padLeft(2, '0')}:${incident.createdAt.minute.toString().padLeft(2, '0')}',
                    style: const TextStyle(fontSize: 11, color: _muted),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right, size: 18, color: _muted),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class PriorityPill extends StatelessWidget {
  const PriorityPill({super.key, required this.priority});
  final Priority priority;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: priorityColor(priority).withValues(alpha: .1),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Text(
      priorityName(priority).toUpperCase(),
      style: TextStyle(
        fontSize: 9,
        fontWeight: FontWeight.w800,
        letterSpacing: .6,
        color: priorityColor(priority),
      ),
    ),
  );
}

class RespondersPage extends StatelessWidget {
  const RespondersPage({super.key, required this.store});
  final OperationsStore store;
  @override
  Widget build(BuildContext context) => PagePad(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Panel(
          child: Text(
            'Availability and suitability are refreshed from this device’s simulated workspace. Responders assigned to an active case are excluded from new recommendations.',
            style: TextStyle(color: _muted, height: 1.45),
          ),
        ),
        const SectionTitle('Field teams'),
        ...store.responders.map(
          (r) => Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: Panel(
              child: Column(
                children: [
                  ResponderRow(responder: r, store: store),
                  if (r.incidentId == null)
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        onPressed: () => store.setAvailability(
                          r,
                          r.status != ResponderStatus.available,
                        ),
                        icon: Icon(
                          r.status == ResponderStatus.available
                              ? Icons.pause_circle_outline
                              : Icons.play_circle_outline,
                        ),
                        label: Text(
                          r.status == ResponderStatus.available
                              ? 'Set off duty'
                              : 'Set available',
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

class ResponderRow extends StatelessWidget {
  const ResponderRow({
    super.key,
    required this.responder,
    required this.store,
    this.compact = false,
  });
  final Responder responder;
  final OperationsStore store;
  final bool compact;
  @override
  Widget build(BuildContext context) {
    final incident = store.incidents
        .where((i) => i.id == responder.incidentId)
        .firstOrNull;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: compact ? 7 : 2),
      child: Row(
        children: [
          CircleAvatar(
            radius: compact ? 17 : 21,
            backgroundColor: const Color(0xFFF1EDEA),
            child: Text(
              responder.name.split(' ').map((x) => x[0]).take(2).join(),
              style: TextStyle(
                color: const Color(0xFF9B443A),
                fontWeight: FontWeight.bold,
                fontSize: compact ? 11 : 13,
              ),
            ),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  responder.name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: _ink,
                  ),
                ),
                Text(
                  responder.team,
                  style: const TextStyle(color: _muted, fontSize: 11),
                ),
                if (!compact)
                  Text(
                    'Skills: ${responder.skills.join(' · ')}${incident == null ? '' : '  •  ${incident.type} at ${incident.location}'}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: _muted, fontSize: 11),
                  ),
              ],
            ),
          ),
          StatusPill(text: responderStatusName(responder.status)),
        ],
      ),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    final c = statusColor(text);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: c.withValues(alpha: .1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 10),
      ),
    );
  }
}

class ResourcesPage extends StatelessWidget {
  const ResourcesPage({super.key, required this.store});
  final OperationsStore store;
  @override
  Widget build(BuildContext context) => PagePad(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Panel(
          child: Text(
            'Resource assignments are simulated and exclusive per active incident. Allocation is made with responder assignment and released when a case is resolved.',
            style: TextStyle(color: _muted, height: 1.45),
          ),
        ),
        const SectionTitle('Equipment & vehicles'),
        ...store.resources.map((r) {
          final incident = store.incidents
              .where((i) => i.id == r.incidentId)
              .firstOrNull;
          return Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: Panel(
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F3F6),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      r.type == 'Medical'
                          ? Icons.medical_services_outlined
                          : r.type == 'Fire'
                          ? Icons.local_fire_department_outlined
                          : Icons.directions_car_outlined,
                      color: _ink,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          r.name,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            color: _ink,
                          ),
                        ),
                        Text(
                          '${r.type} response',
                          style: const TextStyle(color: _muted, fontSize: 11),
                        ),
                        if (incident != null)
                          Text(
                            'Assigned: ${incident.location}',
                            style: const TextStyle(color: _muted, fontSize: 11),
                          ),
                      ],
                    ),
                  ),
                  StatusPill(text: r.available ? 'Available' : 'Allocated'),
                ],
              ),
            ),
          );
        }),
      ],
    ),
  );
}

class ReportsPage extends StatelessWidget {
  const ReportsPage({super.key, required this.store});
  final OperationsStore store;
  @override
  Widget build(BuildContext context) {
    final resolved = store.history.length;
    final total = store.incidents.length;
    final avg = resolved == 0
        ? '—'
        : '${(store.history.map((i) => (i.resolvedAt ?? i.createdAt).difference(i.createdAt).inMinutes).reduce((a, b) => a + b) / resolved).toStringAsFixed(0)} min';
    return PagePad(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Panel(
            child: Text(
              'Local operational summary based on records on this device. Use simulated records for classroom demonstration only.',
              style: TextStyle(color: _muted, height: 1.4),
            ),
          ),
          const SectionTitle('Operation summary'),
          LayoutBuilder(
            builder: (context, constraints) => Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                MetricCard(
                  label: 'Total cases',
                  value: '$total',
                  icon: Icons.assignment_outlined,
                  accent: const Color(0xFF3569A8),
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Resolved',
                  value: '$resolved',
                  icon: Icons.task_alt_outlined,
                  accent: const Color(0xFF327A5B),
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Avg. resolution',
                  value: avg,
                  icon: Icons.schedule_outlined,
                  accent: const Color(0xFFAD7411),
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Available teams',
                  value:
                      '${store.responders.where((r) => r.status == ResponderStatus.available).length}',
                  icon: Icons.groups_outlined,
                  accent: const Color(0xFF327A5B),
                  width: (constraints.maxWidth - 10) / 2,
                ),
              ],
            ),
          ),
          const SectionTitle('Incident history'),
          if (store.incidents.isEmpty)
            const EmptyPanel(
              icon: Icons.history,
              title: 'No operation history',
              detail: 'Completed cases will appear here.',
            )
          else
            ...store.history.map(
              (i) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Panel(
                  child: Row(
                    children: [
                      Icon(
                        Icons.check_circle_outline,
                        color: statusColor('Resolved'),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${i.type} • ${priorityName(i.priority)}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                color: _ink,
                              ),
                            ),
                            Text(
                              '${i.location} · ${i.resolvedAt?.toLocal().toString().substring(0, 16) ?? ''}',
                              style: const TextStyle(
                                color: _muted,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          const SectionTitle('Audit trail'),
          if (store.events.isEmpty)
            const EmptyPanel(
              icon: Icons.receipt_long_outlined,
              title: 'No activity recorded',
              detail: 'Actions will be recorded here.',
            )
          else
            Panel(
              child: Column(
                children: store.events
                    .take(30)
                    .map((e) => ActivityRow(event: e))
                    .toList(),
              ),
            ),
        ],
      ),
    );
  }
}

class ActivityRow extends StatelessWidget {
  const ActivityRow({super.key, required this.event});
  final ActivityEvent event;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.circle, size: 8, color: Color(0xFFB64032)),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                event.title,
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  color: _ink,
                  fontSize: 12,
                ),
              ),
              Text(
                event.detail,
                style: const TextStyle(color: _muted, fontSize: 11),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        Text(
          '${event.at.hour.toString().padLeft(2, '0')}:${event.at.minute.toString().padLeft(2, '0')}',
          style: const TextStyle(color: _muted, fontSize: 10),
        ),
      ],
    ),
  );
}

class EmptyPanel extends StatelessWidget {
  const EmptyPanel({
    super.key,
    required this.icon,
    required this.title,
    required this.detail,
  });
  final IconData icon;
  final String title, detail;
  @override
  Widget build(BuildContext context) => Panel(
    child: SizedBox(
      width: double.infinity,
      child: Column(
        children: [
          Icon(icon, size: 30, color: _muted),
          const SizedBox(height: 9),
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700, color: _ink),
          ),
          const SizedBox(height: 4),
          Text(
            detail,
            textAlign: TextAlign.center,
            style: const TextStyle(color: _muted, fontSize: 12),
          ),
        ],
      ),
    ),
  );
}

class StorageWarning extends StatelessWidget {
  const StorageWarning({super.key, required this.text});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: const Color(0xFFFFF3F0),
      border: Border.all(color: const Color(0xFFE5B9AF)),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      text,
      style: const TextStyle(color: Color(0xFF8A271E), fontSize: 12),
    ),
  );
}

const _locations = <String, ({double lat, double lon})>{
  'Sector 68, Mohali': (lat: 30.7047, lon: 76.7185),
  'Phase 6, Mohali': (lat: 30.7040, lon: 76.7290),
  'Sector 70, Mohali': (lat: 30.6990, lon: 76.7130),
  'Phase 3B2, Mohali': (lat: 30.7105, lon: 76.7150),
  'Sector 61, Mohali': (lat: 30.7200, lon: 76.7120),
  'Landmark / other': (lat: 30.7080, lon: 76.7200),
};

Future<void> showCreateIncident(
  BuildContext context,
  OperationsStore store,
) async {
  final form = GlobalKey<FormState>();
  final description = TextEditingController();
  final locationText = TextEditingController(text: _locations.keys.first);
  String type = 'Medical';
  String place = _locations.keys.first;
  int severity = 3, urgency = 3;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) => StatefulBuilder(
      builder: (context, setState) {
        final decision = assessPriority(
          type: type,
          severity: severity,
          urgency: urgency,
        );
        return Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            0,
            20,
            MediaQuery.of(context).viewInsets.bottom + 20,
          ),
          child: Form(
            key: form,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Register emergency request',
                    style: Theme.of(context).textTheme.titleLarge
                        ?.copyWith(fontWeight: FontWeight.w800, color: _ink),
                  ),
                  const SizedBox(height: 5),
                  const Text(
                    'Training record only. No emergency service is contacted.',
                    style: TextStyle(color: _muted, fontSize: 12),
                  ),
                  const SizedBox(height: 18),
                  DropdownButtonFormField<String>(
                    initialValue: type,
                    decoration: const InputDecoration(
                      labelText: 'Incident type',
                    ),
                    items: ['Medical', 'Fire', 'Rescue', 'Security', 'Utility']
                        .map((x) => DropdownMenuItem(value: x, child: Text(x)))
                        .toList(),
                    onChanged: (v) => setState(() => type = v ?? type),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: description,
                    minLines: 2,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'What happened?',
                      hintText: 'Briefly describe the reported situation',
                    ),
                    validator: (v) => v == null || v.trim().isEmpty
                        ? 'Add a short incident description.'
                        : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: place,
                    decoration: const InputDecoration(
                      labelText: 'Simulated incident location',
                    ),
                    items: _locations.keys
                        .map((x) => DropdownMenuItem(value: x, child: Text(x)))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) {
                        setState(() {
                          place = v;
                          locationText.text = v == 'Landmark / other' ? '' : v;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: locationText,
                    decoration: const InputDecoration(
                      labelText: 'Location or landmark',
                    ),
                    validator: (v) => v == null || v.trim().isEmpty
                        ? 'Enter the incident location.'
                        : null,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Severity  $severity / 5',
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: _ink,
                    ),
                  ),
                  Slider(
                    value: severity.toDouble(),
                    min: 1,
                    max: 5,
                    divisions: 4,
                    label: '$severity',
                    onChanged: (v) => setState(() => severity = v.round()),
                  ),
                  Text(
                    'Reported urgency  $urgency / 5',
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: _ink,
                    ),
                  ),
                  Slider(
                    value: urgency.toDouble(),
                    min: 1,
                    max: 5,
                    divisions: 4,
                    label: '$urgency',
                    onChanged: (v) => setState(() => urgency = v.round()),
                  ),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: priorityColor(decision.priority)
                          .withValues(alpha: .08),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '${priorityName(decision.priority).toUpperCase()} PRIORITY  ·  ${decision.reason}',
                      style: TextStyle(
                        color: priorityColor(decision.priority),
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () {
                        if (!form.currentState!.validate()) return;
                        final pos = _locations[place]!;
                        store
                            .createIncident(
                              type: type,
                              description: description.text,
                              location: locationText.text.trim(),
                              lat: pos.lat,
                              lon: pos.lon,
                              severity: severity,
                              urgency: urgency,
                            )
                            .then((_) {
                              if (sheetContext.mounted) {
                                Navigator.pop(sheetContext);
                              }
                            })
                            .catchError((Object e) {
                              if (context.mounted) {
                                ScaffoldMessenger.of(
                                  context,
                                ).showSnackBar(SnackBar(content: Text('$e')));
                              }
                            });
                      },
                      icon: const Icon(Icons.add_task),
                      label: const Text('Register incident'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    ),
  );
  description.dispose();
  locationText.dispose();
}

void openIncident(
  BuildContext context,
  OperationsStore store,
  Incident incident,
) => Navigator.push(
  context,
  MaterialPageRoute<void>(
    builder: (_) => IncidentDetailPage(store: store, incident: incident),
  ),
);

class IncidentDetailPage extends StatefulWidget {
  const IncidentDetailPage({
    super.key,
    required this.store,
    required this.incident,
  });
  final OperationsStore store;
  final Incident incident;
  @override
  State<IncidentDetailPage> createState() => _IncidentDetailPageState();
}

class _IncidentDetailPageState extends State<IncidentDetailPage> {
  final message = TextEditingController();
  bool busy = false;
  Future<void> run(Future<void> Function() action) async {
    setState(() => busy = true);
    try {
      await action();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString().replaceFirst('Bad state: ', ''))),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final store = widget.store;
    final i = widget.incident;
    final responder = store.responders
        .where((r) => r.id == i.responderId)
        .firstOrNull;
    final suggestions = i.status == IncidentStatus.queued
        ? store.recommendations(i)
        : <Responder>[];
    final resource = store.resources
        .where((r) => r.id == i.resourceId)
        .firstOrNull;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) => Scaffold(
        appBar: AppBar(title: const Text('Incident details')),
        body: PagePad(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (store.storageError != null)
                StorageWarning(text: store.storageError!),
              Row(
                children: [
                  PriorityPill(priority: i.priority),
                  const Spacer(),
                  StatusPill(text: incidentStatusName(i.status)),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                i.type,
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800, color: _ink),
              ),
              const SizedBox(height: 7),
              Text(
                i.description,
                style: const TextStyle(color: _muted, height: 1.45),
              ),
              const SectionTitle('Incident information'),
              Panel(
                child: Column(
                  children: [
                    InfoRow(
                      icon: Icons.place_outlined,
                      label: 'Location',
                      value: i.location,
                    ),
                    InfoRow(
                      icon: Icons.schedule,
                      label: 'Reported',
                      value: i.createdAt.toLocal().toString().substring(0, 16),
                    ),
                    InfoRow(
                      icon: Icons.health_and_safety_outlined,
                      label: 'Assessment',
                      value:
                          'Severity ${i.severity}/5 · urgency ${i.urgency}/5',
                    ),
                    InfoRow(
                      icon: Icons.insights_outlined,
                      label: 'Priority rationale',
                      value: i.priorityReason,
                    ),
                  ],
                ),
              ),
              if (i.active && i.status == IncidentStatus.queued) ...[
                SectionTitle(
                  'Responder recommendation',
                  trailing: Text(
                    '${suggestions.length} ELIGIBLE',
                    style: const TextStyle(
                      fontSize: 10,
                      color: _muted,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                if (suggestions.isEmpty)
                  const Panel(
                    child: Text(
                      'No available responder currently matches this incident type. Keep it queued while a coordinator reviews resource coverage.',
                      style: TextStyle(color: _muted, height: 1.4),
                    ),
                  )
                else
                  ...suggestions.map((r) {
                    final km = distanceKm(
                      r.latitude,
                      r.longitude,
                      i.latitude,
                      i.longitude,
                    );
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Panel(
                        child: Row(
                          children: [
                            const Icon(
                              Icons.person_pin_circle_outlined,
                              color: Color(0xFF3569A8),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    r.name,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      color: _ink,
                                    ),
                                  ),
                                  Text(
                                    '${r.team} · ${km.toStringAsFixed(1)} km · ${r.skills.join(', ')}',
                                    style: const TextStyle(
                                      color: _muted,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            FilledButton.tonal(
                              onPressed: busy
                                  ? null
                                  : () => run(() => store.assign(i, r)),
                              child: const Text('Assign'),
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
              ],
              if (responder != null) ...[
                const SectionTitle('Assigned response'),
                Panel(
                  child: Column(
                    children: [
                      InfoRow(
                        icon: Icons.person_outline,
                        label: 'Responder',
                        value: responder.name,
                      ),
                      InfoRow(
                        icon: Icons.directions_car_outlined,
                        label: 'Resource',
                        value: resource?.name ?? 'No unit available',
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: busy || i.status == IncidentStatus.resolved
                              ? null
                              : () => run(() => store.advance(i)),
                          icon: Icon(
                            i.status == IncidentStatus.responding
                                ? Icons.check_circle_outline
                                : Icons.arrow_forward,
                          ),
                          label: Text(
                            i.status == IncidentStatus.assigned
                                ? 'Mark en route'
                                : i.status == IncidentStatus.enRoute
                                ? 'Mark responding'
                                : i.status == IncidentStatus.responding
                                ? 'Resolve incident'
                                : 'Resolved',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              if (i.active) ...[
                const SectionTitle('Coordination messages'),
                Panel(
                  child: Column(
                    children: [
                      ...store
                          .thread(i.id)
                          .map((m) => MessageBubble(message: m)),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Expanded(
                            child: TextField(
                              controller: message,
                              minLines: 1,
                              maxLines: 3,
                              decoration: const InputDecoration(
                                hintText: 'Add an update to this incident',
                                isDense: true,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton.filled(
                            tooltip: 'Send message',
                            onPressed: busy
                                ? null
                                : () {
                                    final value = message.text;
                                    run(
                                      () => store.sendMessage(
                                        i,
                                        sender: 'Coordinator',
                                        role: 'Coordinator',
                                        body: value,
                                      ),
                                    ).then((_) {
                                      message.clear();
                                    });
                                  },
                            icon: const Icon(Icons.send),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
              const SectionTitle('Activity history'),
              Panel(
                child: Column(
                  children: store
                      .incidentEvents(i.id)
                      .map((e) => ActivityRow(event: e))
                      .toList(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class InfoRow extends StatelessWidget {
  const InfoRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
  });
  final IconData icon;
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 17, color: _muted),
        const SizedBox(width: 9),
        SizedBox(
          width: 104,
          child: Text(
            label,
            style: const TextStyle(color: _muted, fontSize: 12),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: _ink,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}

class MessageBubble extends StatelessWidget {
  const MessageBubble({super.key, required this.message});
  final ChatMessage message;
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 9),
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      color: const Color(0xFFF5F6F8),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              message.sender,
              style: const TextStyle(
                color: _ink,
                fontWeight: FontWeight.w700,
                fontSize: 11,
              ),
            ),
            const Spacer(),
            Text(
              '${message.sentAt.hour.toString().padLeft(2, '0')}:${message.sentAt.minute.toString().padLeft(2, '0')}',
              style: const TextStyle(color: _muted, fontSize: 10),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(message.body, style: const TextStyle(color: _ink, fontSize: 12)),
      ],
    ),
  );
}

class ResponderWorkspace extends StatefulWidget {
  const ResponderWorkspace({super.key, required this.store});
  final OperationsStore store;
  @override
  State<ResponderWorkspace> createState() => _ResponderWorkspaceState();
}

class _ResponderWorkspaceState extends State<ResponderWorkspace> {
  String? selectedId;
  final message = TextEditingController();
  @override
  void dispose() {
    message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.store,
    builder: (context, _) {
      final store = widget.store;
      selectedId ??= store.responders.firstOrNull?.id;
      final person = store.responders
          .where((r) => r.id == selectedId)
          .firstOrNull;
      final incident = person?.incidentId == null
          ? null
          : store.incidents
                .where((i) => i.id == person!.incidentId)
                .firstOrNull;
      final content = <Widget>[
        const Panel(
          child: Text(
            'Simulated responder view on this device. This selector does not authenticate a user or deliver messages to another device.',
            style: TextStyle(color: _muted, height: 1.4),
          ),
        ),
        const SectionTitle('Choose responder'),
      ];
      if (person == null) {
        content.add(
          const EmptyPanel(
            icon: Icons.person_off_outlined,
            title: 'No responder profile',
            detail: 'Add a simulated responder to continue.',
          ),
        );
      } else {
        content.add(
          DropdownButtonFormField<String>(
            initialValue: selectedId,
            decoration: const InputDecoration(labelText: 'Training profile'),
            items: store.responders
                .map(
                  (r) => DropdownMenuItem(
                    value: r.id,
                    child: Text('${r.name} · ${r.team}'),
                  ),
                )
                .toList(),
            onChanged: (v) => setState(() => selectedId = v),
          ),
        );
        if (incident == null) {
          content.add(const SizedBox(height: 14));
          content.add(
            Panel(
              child: Column(
                children: [
                  StatusPill(text: responderStatusName(person.status)),
                  const SizedBox(height: 12),
                  const Icon(
                    Icons.task_alt_outlined,
                    size: 36,
                    color: Color(0xFF327A5B),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'No active assignment',
                    style: TextStyle(fontWeight: FontWeight.w700, color: _ink),
                  ),
                  const Text(
                    'New assignments will appear in this workspace.',
                    style: TextStyle(color: _muted, fontSize: 12),
                  ),
                ],
              ),
            ),
          );
        } else {
          content.addAll([
            const SectionTitle('Current assignment'),
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      PriorityPill(priority: incident.priority),
                      const Spacer(),
                      StatusPill(text: incidentStatusName(incident.status)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    incident.type,
                    style: Theme.of(context).textTheme.titleLarge
                        ?.copyWith(fontWeight: FontWeight.w800, color: _ink),
                  ),
                  Text(
                    incident.location,
                    style: const TextStyle(color: _muted),
                  ),
                  const Divider(height: 24),
                  Text(
                    incident.description,
                    style: const TextStyle(color: _ink, height: 1.4),
                  ),
                  const SizedBox(height: 15),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: incident.status == IncidentStatus.resolved
                          ? null
                          : () async {
                              try {
                                await store.advance(incident);
                              } catch (e) {
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text(e.toString())),
                                  );
                                }
                              }
                            },
                      icon: const Icon(Icons.arrow_forward),
                      label: Text(
                        incident.status == IncidentStatus.assigned
                            ? 'Acknowledge & en route'
                            : incident.status == IncidentStatus.enRoute
                            ? 'Arrived · start response'
                            : incident.status == IncidentStatus.responding
                            ? 'Mark operation complete'
                            : 'Completed',
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SectionTitle('Incident coordination'),
            Panel(
              child: Column(
                children: [
                  ...store
                      .thread(incident.id)
                      .map((m) => MessageBubble(message: m)),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: message,
                          decoration: const InputDecoration(
                            hintText: 'Send an update',
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filled(
                        tooltip: 'Send update',
                        onPressed: () {
                          final text = message.text;
                          store
                              .sendMessage(
                                incident,
                                sender: person.name,
                                role: 'Responder',
                                body: text,
                              )
                              .then((_) {
                                message.clear();
                              });
                        },
                        icon: const Icon(Icons.send),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ]);
        }
      }
      return Scaffold(
        appBar: AppBar(
          title: const Text('Responder workspace'),
          actions: [
            IconButton(
              tooltip: 'Back to coordinator console',
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.dashboard_outlined),
            ),
          ],
        ),
        body: PagePad(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: content,
          ),
        ),
      );
    },
  );
}
