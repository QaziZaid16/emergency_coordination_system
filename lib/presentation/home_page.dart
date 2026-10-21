import 'package:flutter/material.dart';

import '../data/operations_store.dart';
import '../domain/dispatch_rules.dart';
import '../domain/models.dart';
import 'design_system.dart';

const _ink = OpsColors.ink;
const _muted = OpsColors.muted;
const _line = OpsColors.line;

Color priorityColor(Priority p) => switch (p) {
  Priority.critical => OpsColors.critical,
  Priority.high => OpsColors.accent,
  Priority.medium => OpsColors.warning,
  Priority.low => OpsColors.success,
};
Color statusColor(String s) =>
    s.toLowerCase().contains('available') || s == 'Resolved'
    ? OpsColors.success
    : s.toLowerCase().contains('off')
    ? OpsColors.muted
    : OpsColors.blue;

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
        title: Text(
          titles[index],
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Switch workspace',
            icon: const CircleAvatar(
              radius: 17,
              backgroundColor: OpsColors.primaryWash,
              child: Icon(
                Icons.swap_horiz_rounded,
                color: OpsColors.primaryDark,
                size: 20,
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14),
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
                child: Text('Responder workspace · demo'),
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
    padding: const EdgeInsets.fromLTRB(
      OpsSpace.lg,
      OpsSpace.sm,
      OpsSpace.lg,
      OpsSpace.xxl,
    ),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: OpsSpace.contentMax),
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
    padding: const EdgeInsets.only(top: 23, bottom: 11),
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
          const _TrainingBanner(),
          const SizedBox(height: 15),
          LayoutBuilder(
            builder: (context, c) {
              final width = (c.maxWidth - 12) / 2;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  MetricCard(
                    label: 'Active incidents',
                    value: '${active.length}',
                    icon: Icons.warning_amber_rounded,
                    accent: OpsColors.accent,
                    width: width,
                  ),
                  MetricCard(
                    label: 'Critical priority',
                    value: '$critical',
                    icon: Icons.priority_high_rounded,
                    accent: priorityColor(Priority.critical),
                    width: width,
                  ),
                  MetricCard(
                    label: 'Teams assigned',
                    value: '$assigned',
                    icon: Icons.route_outlined,
                    accent: OpsColors.blue,
                    width: width,
                  ),
                  MetricCard(
                    label: 'Teams available',
                    value: '$available',
                    icon: Icons.groups_2_outlined,
                    accent: OpsColors.success,
                    width: width,
                  ),
                ],
              );
            },
          ),
          SectionTitle(
            'Priority queue',
            trailing: _CountTag(text: '${active.length} OPEN'),
          ),
          if (active.isEmpty)
            const EmptyPanel(
              icon: Icons.check_circle_outline_rounded,
              title: 'All clear in the training queue',
              detail: 'New simulated requests will appear here for review.',
            )
          else
            ...active
                .take(4)
                .map(
                  (i) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: IncidentTile(
                      incident: i,
                      store: store,
                      onTap: () => onOpenIncident(i),
                    ),
                  ),
                ),
          SectionTitle(
            'Team readiness',
            trailing: _CountTag(text: '$assigned DEPLOYED'),
          ),
          Panel(
            padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
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

class _TrainingBanner extends StatelessWidget {
  const _TrainingBanner();
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: OpsColors.surfaceRaised,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: .12),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Icon(Icons.hub_rounded, color: Colors.white),
        ),
        const SizedBox(width: 13),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Local operations desk',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                ),
              ),
              SizedBox(height: 3),
              Text(
                'Simulated records · no live dispatch',
                style: TextStyle(
                  color: Color(0xFFD0E4E1),
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
        const Icon(Icons.shield_outlined, color: OpsColors.success, size: 23),
      ],
    ),
  );
}

class _CountTag extends StatelessWidget {
  const _CountTag({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: OpsColors.primaryWash,
      borderRadius: BorderRadius.circular(99),
    ),
    child: Text(
      text,
      style: const TextStyle(
        color: OpsColors.primaryDark,
        fontWeight: FontWeight.w800,
        fontSize: 9,
        letterSpacing: .5,
      ),
    ),
  );
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
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: .1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: accent, size: 19),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 22,
                    height: 1.05,
                    fontWeight: FontWeight.w800,
                    color: _ink,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 10,
                    color: _muted,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
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
  final searchController = TextEditingController();

  @override
  void dispose() {
    searchController.dispose();
    super.dispose();
  }

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
            controller: searchController,
            decoration: InputDecoration(
              prefixIcon: Icon(Icons.search),
              hintText: 'Search type, location, or details',
              suffixIcon: query.isEmpty
                  ? null
                  : IconButton(
                      tooltip: 'Clear search',
                      onPressed: () {
                        searchController.clear();
                        setState(() => query = '');
                      },
                      icon: const Icon(Icons.close_rounded),
                    ),
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
          SectionTitle(
            filter == 'Resolved' ? 'Completed cases' : 'Cases',
            trailing: _CountTag(text: '${filtered.length} FOUND'),
          ),
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
      color: OpsColors.surface,
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
                    color: responder == null ? _muted : OpsColors.blue,
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
            'Training roster · Assigned teams are excluded from new recommendations.',
            style: TextStyle(color: OpsColors.inkSoft, height: 1.35),
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
            backgroundColor: OpsColors.surfaceRaised,
            child: Text(
              responder.name.split(' ').map((x) => x[0]).take(2).join(),
              style: TextStyle(
                color: OpsColors.primaryDark,
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
            'Sample inventory · Units reserve with assignment and release at resolution.',
            style: TextStyle(color: OpsColors.inkSoft, height: 1.35),
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
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: OpsColors.primaryWash,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      r.type == 'Medical'
                          ? Icons.medical_services_outlined
                          : r.type == 'Fire'
                          ? Icons.local_fire_department_outlined
                          : Icons.directions_car_outlined,
                      color: OpsColors.primaryDark,
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
              'Local summary · Based only on this device’s training records.',
              style: TextStyle(color: OpsColors.inkSoft, height: 1.35),
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
                  accent: OpsColors.blue,
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Resolved',
                  value: '$resolved',
                  icon: Icons.task_alt_outlined,
                  accent: OpsColors.success,
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Avg. resolution',
                  value: avg,
                  icon: Icons.schedule_outlined,
                  accent: OpsColors.warning,
                  width: (constraints.maxWidth - 10) / 2,
                ),
                MetricCard(
                  label: 'Available teams',
                  value:
                      '${store.responders.where((r) => r.status == ResponderStatus.available).length}',
                  icon: Icons.groups_outlined,
                  accent: OpsColors.success,
                  width: (constraints.maxWidth - 10) / 2,
                ),
              ],
            ),
          ),
          const SectionTitle('Incident history'),
          if (store.history.isEmpty)
            const EmptyPanel(
              icon: Icons.history,
              title: 'No completed cases yet',
              detail: 'Resolved training incidents will appear here.',
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
        const Icon(Icons.circle, size: 8, color: OpsColors.primary),
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
          Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(
              color: OpsColors.primaryWash,
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 23, color: OpsColors.primaryDark),
          ),
          const SizedBox(height: 12),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontWeight: FontWeight.w800,
              color: _ink,
              fontSize: 15,
            ),
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
      color: OpsColors.criticalWash,
      border: Border.all(color: OpsColors.critical.withValues(alpha: .35)),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      text,
      style: const TextStyle(color: OpsColors.critical, fontSize: 12),
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
              const SectionTitle('Response progress'),
              LifecycleProgress(status: i.status),
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
                              color: OpsColors.blue,
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

class LifecycleProgress extends StatelessWidget {
  const LifecycleProgress({super.key, required this.status});
  final IncidentStatus status;

  @override
  Widget build(BuildContext context) {
    const labels = ['Queued', 'Assigned', 'En route', 'Responding', 'Resolved'];
    final current = status.index;
    return Panel(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'CASE LIFECYCLE',
                  style: TextStyle(
                    color: _muted,
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                    letterSpacing: .8,
                  ),
                ),
              ),
              Text(
                'STEP ${current + 1} OF ${labels.length}',
                style: const TextStyle(
                  color: OpsColors.primaryDark,
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: .6,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: LinearProgressIndicator(
              value: current / (labels.length - 1),
              minHeight: 6,
              backgroundColor: OpsColors.primaryWash,
              color: OpsColors.primary,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              for (var index = 0; index < labels.length; index++)
                Expanded(
                  child: Text(
                    labels[index],
                    textAlign: index == 0
                        ? TextAlign.left
                        : index == labels.length - 1
                        ? TextAlign.right
                        : TextAlign.center,
                    style: TextStyle(
                      color: index == current ? OpsColors.primaryDark : _muted,
                      fontSize: 9,
                      fontWeight: index == current
                          ? FontWeight.w800
                          : FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
        ],
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
      color: OpsColors.surfaceRaised,
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
                    color: OpsColors.success,
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
