import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../data/api_client.dart';
import '../data/operations_store.dart';
import 'design_system.dart';
import 'home_page.dart';

class CoordinationBrandMark extends StatelessWidget {
  const CoordinationBrandMark({super.key, this.size = 48});
  final double size;

  @override
  Widget build(BuildContext context) => Semantics(
    image: true,
    label: 'IERCS app icon',
    child: ClipRRect(
      borderRadius: BorderRadius.circular(size * .22),
      child: ColoredBox(
        color: OpsColors.surfaceRaised,
        child: Image.asset(
          'assets/branding/iercs_app_icon.png',
          width: size,
          height: size,
          fit: BoxFit.cover,
        ),
      ),
    ),
  );
}

class PortalEntryPage extends StatefulWidget {
  const PortalEntryPage({super.key, required this.api, this.trainingStore});
  final ApiClient api;
  final OperationsStore? trainingStore;
  @override
  State<PortalEntryPage> createState() => _PortalEntryPageState();
}

class _PortalEntryPageState extends State<PortalEntryPage> {
  ApiSession? session;
  bool restoring = true;
  bool onboardingRequired = false;
  String? restoreError;

  @override
  void initState() {
    super.initState();
    widget.api.sessionExpired.addListener(_onSessionExpired);
    _restore();
  }

  @override
  void dispose() {
    widget.api.sessionExpired.removeListener(_onSessionExpired);
    super.dispose();
  }

  void _onSessionExpired() {
    if (!widget.api.sessionExpired.value || !mounted || session == null) return;
    widget.api.sessionExpired.value = false;
    setState(() {
      session = null;
      restoreError = 'Your session expired or was revoked. Sign in again.';
    });
    unawaited(widget.api.clearStoredSession().catchError((_) {}));
  }

  Future<void> _restore() async {
    setState(() {
      restoring = true;
      restoreError = null;
    });
    try {
      final saved = await widget.api.restoreSession();
      if (!mounted) return;
      final onboardingDone = await widget.api.hasCompletedOnboarding();
      if (!mounted) return;
      setState(() {
        session = saved;
        onboardingRequired = saved == null && !onboardingDone;
        restoring = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      final onboardingDone = await widget.api.hasCompletedOnboarding();
      if (!mounted) return;
      setState(() {
        session = null;
        onboardingRequired = !onboardingDone;
        // An absent API origin is a deployment configuration state, not a
        // signed-out user's error. Keep the login clean until they try to sign in.
        restoreError = widget.api.configured ? e.message : null;
        restoring = false;
      });
    } catch (_) {
      if (!mounted) return;
      final onboardingDone = await widget.api.hasCompletedOnboarding();
      if (!mounted) return;
      setState(() {
        session = null;
        onboardingRequired = !onboardingDone;
        restoreError = widget.api.configured
            ? 'Could not verify this device session. Check the service and retry.'
            : null;
        restoring = false;
      });
    }
  }

  Future<void> _completeOnboarding() async {
    await widget.api.completeOnboarding();
    if (mounted) setState(() => onboardingRequired = false);
  }

  void _signedIn(ApiSession value) => setState(() {
    widget.api.sessionExpired.value = false;
    session = value;
    restoreError = null;
  });

  Future<void> _logout() async {
    final current = session;
    setState(() {
      session = null;
      restoreError = null;
    });
    var serverRevoked = current == null;
    if (current != null) {
      try {
        await widget.api.logout(current);
        serverRevoked = true;
      } catch (_) {
        serverRevoked = false;
      }
    }
    if (mounted && !serverRevoked) {
      setState(() {
        restoreError = 'Signed out on this device, but the server could not confirm session revocation.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (restoring) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (onboardingRequired && session == null && restoreError == null) {
      return OnboardingPage(onComplete: _completeOnboarding);
    }
    final current = session;
    if (current != null) {
      return switch (current.role) {
        'admin' || 'super_admin' => Scaffold(
          appBar: AppBar(title: const Text('Administration')),
          body: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.desktop_windows_outlined, size: 54),
                  const SizedBox(height: 16),
                  const Text(
                    'Administration is available in the web dashboard.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  const SelectableText(
                    'Open the administration dashboard in your browser.',
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton(
                    onPressed: _logout,
                    child: const Text('Sign out'),
                  ),
                ],
              ),
            ),
          ),
        ),
        'responder' => ResponderPortal(
          api: widget.api,
          session: current,
          onLogout: _logout,
        ),
        _ => UserPortal(api: widget.api, session: current, onLogout: _logout),
      };
    }
    return PortalLoginPage(
      key: const ValueKey('direct-login'),
      api: widget.api,
      trainingStore: widget.trainingStore,
      initialMessage: restoreError,
      onRetrySession: () => unawaited(_restore()),
      onSignedIn: _signedIn,
    );
  }
}

class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key, required this.onComplete});
  final Future<void> Function() onComplete;

  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends State<OnboardingPage> {
  static const slides = [
    (
      'Report an emergency',
      'Share what happened and where. Review the details before sending a request to your coordination service.',
      Icons.crisis_alert_outlined,
    ),
    (
      'Coordinate with clarity',
      'Follow incident status and, when authorized, see responder assignments made by your coordination team.',
      Icons.hub_outlined,
    ),
    (
      'Know what comes next',
      'Check status updates from your account. This app does not contact emergency services or guarantee a response.',
      Icons.notifications_active_outlined,
    ),
  ];
  final controller = PageController();
  int index = 0;
  bool finishing = false;

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> finish() async {
    if (finishing) return;
    setState(() => finishing = true);
    try {
      await widget.onComplete();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not save this step. Please try again.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => finishing = false);
    }
  }

  bool navigating = false;

  Future<void> next() async {
    if (finishing || navigating) return;
    if (index == slides.length - 1) {
      await finish();
      return;
    }
    final nextIndex = index + 1;
    setState(() {
      navigating = true;
      index = nextIndex;
    });
    try {
      await controller.animateToPage(
        nextIndex,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOutCubic,
      );
    } finally {
      if (mounted) setState(() => navigating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLast = index == slides.length - 1;
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 20),
              child: Column(
                children: [
                  Row(
                    children: [
                      const CoordinationBrandMark(size: 42),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Text(
                          'IERCS',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                      TextButton(
                        onPressed: finishing || navigating ? null : finish,
                        child: const Text('Skip'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Expanded(
                    child: PageView.builder(
                      controller: controller,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: slides.length,
                      onPageChanged: (value) => setState(() => index = value),
                      itemBuilder: (context, page) {
                        final slide = slides[page];
                        return Center(
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: 520,
                              maxHeight: constraints.maxHeight,
                            ),
                            child: SingleChildScrollView(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    width: 176,
                                    height: 176,
                                    decoration: BoxDecoration(
                                      color: OpsColors.primaryWash,
                                      borderRadius: BorderRadius.circular(48),
                                      border: Border.all(color: OpsColors.line),
                                    ),
                                    child: Icon(
                                      slide.$3,
                                      size: 76,
                                      color: OpsColors.accent,
                                    ),
                                  ),
                                  const SizedBox(height: 36),
                                  Text(
                                    slide.$1,
                                    textAlign: TextAlign.center,
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineSmall,
                                  ),
                                  const SizedBox(height: 14),
                                  Text(
                                    slide.$2,
                                    textAlign: TextAlign.center,
                                    style: Theme.of(context).textTheme.bodyLarge
                                        ?.copyWith(
                                          height: 1.55,
                                          color: OpsColors.inkSoft,
                                        ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(
                      slides.length,
                      (dot) => Semantics(
                        label:
                            'Slide ${dot + 1} of ${slides.length}${dot == index ? ', current' : ''}',
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          margin: const EdgeInsets.symmetric(horizontal: 4),
                          width: dot == index ? 24 : 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: dot == index
                                ? OpsColors.accent
                                : OpsColors.line,
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      if (index > 0)
                        OutlinedButton(
                          onPressed: finishing || navigating
                              ? null
                              : () async {
                                  final previous = index - 1;
                                  setState(() {
                                    navigating = true;
                                    index = previous;
                                  });
                                  try {
                                    await controller.animateToPage(
                                      previous,
                                      duration: const Duration(
                                        milliseconds: 200,
                                      ),
                                      curve: Curves.easeOut,
                                    );
                                  } finally {
                                    if (mounted) {
                                      setState(() => navigating = false);
                                    }
                                  }
                                },
                          child: const Text('Back'),
                        )
                      else
                        const SizedBox(width: 72),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          onPressed: finishing || navigating ? null : next,
                          child: finishing
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : Text(isLast ? 'Get started' : 'Next'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Development coordination platform · Not an emergency service',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class PortalLoginPage extends StatefulWidget {
  const PortalLoginPage({
    super.key,
    required this.api,
    required this.onSignedIn,
    this.trainingStore,
    this.initialMessage,
    this.onRetrySession,
  });
  final ApiClient api;
  final ValueChanged<ApiSession> onSignedIn;
  final OperationsStore? trainingStore;
  final String? initialMessage;
  final VoidCallback? onRetrySession;
  @override
  State<PortalLoginPage> createState() => _PortalLoginPageState();
}

class _PortalLoginPageState extends State<PortalLoginPage> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController();
  final email = TextEditingController();
  final password = TextEditingController();
  bool registering = false;
  bool busy = false;
  bool obscure = true;
  bool rememberMe = false;
  String? error;

  @override
  void initState() {
    super.initState();
    error = widget.initialMessage;
  }

  @override
  void dispose() {
    name.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!widget.api.configured) {
      setState(
        () => error = registering
            ? 'Account creation is unavailable because this app is not connected to the coordination service. Please contact your service administrator.'
            : 'Sign-in is unavailable because this app is not connected to the coordination service. Please contact your service administrator.',
      );
      return;
    }
    if (!(form.currentState?.validate() ?? false)) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final value = registering
          ? await widget.api.registerUser(
              name.text,
              email.text,
              password.text,
              rememberMe: rememberMe,
            )
          : await widget.api.login(
              email.text,
              password.text,
              'auto',
              rememberMe: rememberMe,
            );
      if (mounted) {
        widget.onSignedIn(value);
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'The service returned an unexpected response. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: ListView(
            padding: const EdgeInsets.all(22),
            shrinkWrap: true,
            children: [
              const Center(child: CoordinationBrandMark(size: 72)),
              const SizedBox(height: 14),
              Text(
                registering ? 'Create your account' : 'Welcome back',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                registering
                    ? 'Register to report and follow incidents.'
                    : 'Sign in to continue to your workspace.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 22),
              Form(
                key: form,
                child: Column(
                  children: [
                    if (registering)
                      TextFormField(
                        controller: name,
                        textCapitalization: TextCapitalization.words,
                        decoration: const InputDecoration(
                          labelText: 'Your name',
                        ),
                        validator: (v) => v == null || v.trim().isEmpty
                            ? 'Enter your name'
                            : null,
                      ),
                    if (registering) const SizedBox(height: 12),
                    TextFormField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [
                        AutofillHints.username,
                        AutofillHints.email,
                      ],
                      decoration: const InputDecoration(
                        labelText: 'Email address',
                      ),
                      validator: (v) =>
                          v == null ||
                              !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                                  .hasMatch(v.trim())
                          ? 'Enter a valid email address'
                          : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: password,
                      obscureText: obscure,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) {
                        if (!busy) submit();
                      },
                      autofillHints: [
                        registering
                            ? AutofillHints.newPassword
                            : AutofillHints.password,
                      ],
                      decoration: InputDecoration(
                        labelText: 'Password',
                        helperText: registering
                            ? 'Use at least 12 characters.'
                            : null,
                        suffixIcon: IconButton(
                          tooltip: obscure ? 'Show password' : 'Hide password',
                          onPressed: () => setState(() => obscure = !obscure),
                          icon: Icon(
                            obscure
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                      ),
                      validator: (v) => v == null || v.length < 12
                          ? 'Use at least 12 characters'
                          : null,
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: const Text('Remember me on this device'),
                      subtitle: Text(
                        rememberMe ? 'Stay signed in for up to 30 days.' : 'Leave this off to sign in again after closing the app.',
                      ),
                      value: rememberMe,
                      onChanged: busy
                          ? null
                          : (value) =>
                                setState(() => rememberMe = value ?? false),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                  ],
                ),
              ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: MaterialBanner(
                    content: Text(error!),
                    leading: const Icon(Icons.info_outline),
                    actions: [
                      TextButton(
                        onPressed: () => setState(() => error = null),
                        child: const Text('Dismiss'),
                      ),
                      if (widget.initialMessage != null &&
                          widget.initialMessage == error)
                        TextButton(
                          onPressed: () {
                            setState(() => error = null);
                            // Startup has already checked once; a retry happens
                            // only when the user explicitly requests it.
                            widget.onRetrySession?.call();
                          },
                          child: const Text('Retry'),
                        ),
                    ],
                  ),
                ),
              const SizedBox(height: 18),
              FilledButton(
                onPressed: busy ? null : submit,
                child: busy
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(registering ? 'Create user account' : 'Sign in'),
              ),
              TextButton(
                onPressed: busy
                    ? null
                    : () => setState(() {
                        registering = !registering;
                        error = null;
                      }),
                child: Text(
                  registering
                      ? 'I already have an account'
                      : 'Create a user account',
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Your account permissions are verified securely at sign-in.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              if (widget.trainingStore != null &&
                  kDebugMode &&
                  const bool.fromEnvironment('ENABLE_TRAINING_WORKSPACE')) ...[
                const SizedBox(height: 16),
                TextButton.icon(
                  onPressed: busy
                      ? null
                      : () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) =>
                                HomePage(store: widget.trainingStore!),
                          ),
                        ),
                  icon: const Icon(Icons.science_outlined),
                  label: const Text(
                    'Developer tools · local training workspace',
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class UserPortal extends StatefulWidget {
  const UserPortal({
    super.key,
    required this.api,
    required this.session,
    required this.onLogout,
  });
  final ApiClient api;
  final ApiSession session;
  final VoidCallback onLogout;
  @override
  State<UserPortal> createState() => _UserPortalState();
}

class _UserPortalState extends State<UserPortal> {
  final description = TextEditingController();
  final manualLocation = TextEditingController();
  final form = GlobalKey<FormState>();
  String service = 'Ambulance / Medical Emergency';
  Position? position;
  bool locating = false;
  bool manual = false;
  bool composing = false;
  bool submitting = false;
  String? locationError;
  String? error;
  String? success;
  String? idempotencyKey;
  List<dynamic> incidents = [];
  Timer? timer;

  @override
  void initState() {
    super.initState();
    refresh();
    timer = Timer.periodic(const Duration(seconds: 12), (_) => refresh());
  }

  @override
  void dispose() {
    timer?.cancel();
    description.dispose();
    manualLocation.dispose();
    super.dispose();
  }

  Future<void> refresh() async {
    try {
      final items = await widget.api.getList('/incidents', widget.session);
      if (mounted) {
        setState(() {
          incidents = items;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> locate() async {
    setState(() {
      locating = true;
      locationError = null;
      position = null;
      manual = false;
    });
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        throw const ApiException(
          'Location services are turned off. Enable GPS or use the manual location option.',
        );
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw const ApiException(
          'Location permission was not granted. Enter a manual location to continue.',
        );
      }
      final current = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 12),
        ),
      );
      if (current.timestamp.isBefore(
        DateTime.now().subtract(const Duration(minutes: 15)),
      )) {
        throw const ApiException(
          'The location reading is too old. Try again or enter a manual location.',
        );
      }
      if (mounted) {
        setState(() {
          position = current;
          manual = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          locationError = e.toString();
          manual = true;
        });
      }
    } finally {
      if (mounted) setState(() => locating = false);
    }
  }

  Future<void> beginRequest() async {
    setState(() {
      composing = true;
      error = null;
      success = null;
      idempotencyKey ??= ApiClient.newIdempotencyKey();
    });
    await locate();
  }

  Future<void> submit() async {
    if (!(form.currentState?.validate() ?? false)) return;
    if (position == null && manualLocation.text.trim().isEmpty) {
      setState(
        () => locationError =
            'A current GPS fix or a manually entered location is required.',
      );
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm emergency request?'),
        content: Text(
          'Service: $service\nLocation: ${position != null ? 'Current device GPS' : manualLocation.text.trim()}\n\nThis submits a request to this coordination system. It does not contact emergency services.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Review'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Submit request'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      submitting = true;
      error = null;
    });
    try {
      final current = position;
      final data = await widget.api.post(
        '/user/incidents',
        widget.session,
        idempotencyKey: idempotencyKey,
        body: {
          'emergency_type': service,
          'description': description.text.trim(),
          'location_label': current == null
              ? manualLocation.text.trim()
              : 'Device GPS (${current.latitude.toStringAsFixed(5)}, ${current.longitude.toStringAsFixed(5)})',
          'location_source': current == null ? 'manual' : 'gps',
          'latitude': current?.latitude,
          'longitude': current?.longitude,
          'accuracy_m': current?.accuracy,
          'location_at': current?.timestamp.toUtc().toIso8601String(),
          'severity': 3,
          'urgency': 3,
        },
      );
      if (!mounted) return;
      setState(() {
        success =
            'Request ${data['reference']} was received by the coordination system. No external emergency service has been contacted.';
        composing = false;
        description.clear();
        manualLocation.clear();
        position = null;
        idempotencyKey = null;
      });
      await _offerIntakeFollowups(data['id'].toString());
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  Future<void> _offerIntakeFollowups(String incidentId) async {
    final controllers = <String, TextEditingController>{};
    try {
      final intake = await widget.api.get(
        '/incidents/$incidentId/intake',
        widget.session,
      );
      final questions = (intake['questions'] as List? ?? const [])
          .take(3)
          .toList();
      if (questions.isEmpty || !mounted) return;
      for (final raw in questions) {
        final item = Map<String, dynamic>.from(raw as Map);
        controllers[item['key'].toString()] = TextEditingController();
      }
      final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Optional details for responders'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Your request is already submitted. You can skip any question or enter “unknown”.',
                ),
                const SizedBox(height: 12),
                for (final raw in questions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: TextField(
                      controller: controllers[(raw as Map)['key'].toString()],
                      maxLength: 500,
                      maxLines: 2,
                      decoration: InputDecoration(
                        labelText: raw['question'] as String,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Skip'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Save details'),
            ),
          ],
        ),
      );
      if (accepted == true && mounted) {
        await widget.api.post(
          '/incidents/$incidentId/intake/answers',
          widget.session,
          body: {
            'answers': controllers.map(
              (key, value) => MapEntry(
                key,
                value.text.trim().isEmpty ? 'unknown' : value.text.trim(),
              ),
            ),
          },
        );
      }
      for (final controller in controllers.values) {
        controller.dispose();
      }
    } catch (_) {
      // Follow-up collection is optional; it must not undo a persisted request.
      for (final controller in controllers.values) {
        controller.dispose();
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: const Padding(
        padding: EdgeInsets.all(8),
        child: CoordinationBrandMark(size: 48),
      ),
      title: const Text('User Portal'),
      actions: [
        IconButton(
          tooltip: 'Notifications',
          onPressed: () =>
              _openNotificationInbox(context, widget.api, widget.session),
          icon: const Icon(Icons.notifications_outlined),
        ),
        IconButton(
          tooltip: 'Refresh requests',
          onPressed: refresh,
          icon: const Icon(Icons.refresh),
        ),
        IconButton(
          tooltip: 'Sign out',
          onPressed: widget.onLogout,
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(18),
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: OpsColors.surfaceRaised,
            border: Border.all(color: OpsColors.line),
            borderRadius: BorderRadius.circular(22),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Request emergency help',
                style: TextStyle(
                  color: OpsColors.ink,
                  fontSize: 23,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Your request is sent to this coordination system. It does not directly call emergency services.',
                style: TextStyle(color: OpsColors.inkSoft),
              ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: OpsColors.primary,
                    foregroundColor: Colors.white,
                    minimumSize: const Size.fromHeight(58),
                  ),
                  onPressed: locating || composing ? null : beginRequest,
                  icon: const Icon(Icons.emergency),
                  label: const Text('SOS · Request help'),
                ),
              ),
            ],
          ),
        ),
        if (composing) ...[
          const SizedBox(height: 18),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Emergency details',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: service,
                      decoration: const InputDecoration(
                        labelText: 'Emergency service',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'Ambulance / Medical Emergency',
                          child: Text('Ambulance / Medical'),
                        ),
                        DropdownMenuItem(
                          value: 'Fire and Rescue',
                          child: Text('Fire and rescue'),
                        ),
                        DropdownMenuItem(
                          value: 'Police / Security',
                          child: Text('Police / security'),
                        ),
                        DropdownMenuItem(
                          value: 'Other Emergency',
                          child: Text('Other emergency'),
                        ),
                      ],
                      onChanged: (v) => setState(() => service = v ?? service),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: description,
                      maxLines: 3,
                      maxLength: 500,
                      decoration: const InputDecoration(
                        labelText: 'What help is needed?',
                        alignLabelWithHint: true,
                      ),
                      validator: (v) => v == null || v.trim().length < 3
                          ? 'Add a short description'
                          : null,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(
                          position != null
                              ? Icons.gps_fixed
                              : manual
                              ? Icons.edit_location_alt
                              : Icons.location_searching,
                          color: position != null
                              ? OpsColors.success
                              : OpsColors.warning,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            locating
                                ? 'Getting current device location…'
                                : position != null
                                ? 'Current GPS · ±${position!.accuracy.round()} m · ${position!.timestamp.toLocal()}'
                                : manual
                                ? 'Manual location required'
                                : 'Location not captured',
                          ),
                        ),
                      ],
                    ),
                    if (locationError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          locationError!,
                          style: const TextStyle(color: OpsColors.warning),
                        ),
                      ),
                    if (position == null) ...[
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: manualLocation,
                        maxLength: 240,
                        decoration: const InputDecoration(
                          labelText: 'Address, area, or landmark',
                        ),
                        validator: (v) => v == null || v.trim().length < 2
                            ? 'Enter a location'
                            : null,
                      ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                          onPressed: locating ? null : locate,
                          icon: const Icon(Icons.my_location),
                          label: const Text('Try GPS again'),
                        ),
                      ),
                    ],
                    const SizedBox(height: 8),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: submitting || locating ? null : submit,
                        icon: submitting
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.send),
                        label: const Text('Review and submit'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
        if (error != null)
          _FeedbackBox(text: error!, color: OpsColors.critical),
        if (success != null)
          _FeedbackBox(text: success!, color: OpsColors.success),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: Text(
                'My requests',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            IconButton(
              tooltip: 'Refresh',
              onPressed: refresh,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        if (incidents.isEmpty)
          const Card(
            child: ListTile(
              leading: Icon(Icons.inbox_outlined),
              title: Text('No requests yet'),
              subtitle: Text(
                'Submitted requests will appear here with their latest system status.',
              ),
            ),
          ),
        for (final raw in incidents)
          _IncidentCard(
            item: Map<String, dynamic>.from(raw as Map),
            onTap: () => _showUpdates(
              context,
              Map<String, dynamic>.from(raw),
              widget.api,
              widget.session,
            ),
          ),
      ],
    ),
  );
}

Future<void> _showUpdates(
  BuildContext context,
  Map<String, dynamic> item,
  ApiClient api,
  ApiSession session,
) async {
  List<dynamic> rows = [];
  Map<String, dynamic>? report;
  try {
    rows = await api.getList('/incidents/${item['id']}/updates', session);
  } catch (_) {}
  try {
    report = await api.get('/incidents/${item['id']}/report', session);
  } catch (_) {}
  if (!context.mounted) return;
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (context) => SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(20),
        shrinkWrap: true,
        children: [
          Text(
            item['reference']?.toString() ?? 'Incident',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text('${item['priority']} · ${item['status']}'),
          if (report != null) ...[
            const Divider(height: 24),
            Text(
              'Resolution report · version ${report['version']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('Outcome: ${(report['content'] as Map)['outcome']}'),
            Text('Cause: ${(report['content'] as Map)['cause']}'),
            const Text(
              'System-generated from persisted incident records; not an independent investigation.',
            ),
          ],
          const Divider(height: 24),
          if (rows.isEmpty) const Text('No updates are recorded yet.'),
          for (final row in rows)
            ListTile(
              leading: const Icon(Icons.history),
              title: Text(row['message'].toString()),
              subtitle: Text(
                [
                  if (row['original_message'] != null)
                    'Original: ${row['original_message']}',
                  if (row['ai_assisted'] == true)
                    'AI-assisted · responder accepted',
                  row['created_at'].toString(),
                ].join('\n'),
              ),
            ),
        ],
      ),
    ),
  );
}

class AdminPortal extends StatefulWidget {
  const AdminPortal({
    super.key,
    required this.api,
    required this.session,
    required this.onLogout,
  });
  final ApiClient api;
  final ApiSession session;
  final VoidCallback onLogout;
  @override
  State<AdminPortal> createState() => _AdminPortalState();
}

class _AdminPortalState extends State<AdminPortal> {
  Map<String, dynamic> dashboard = {};
  List<dynamic> incidents = [],
      responders = [],
      resources = [],
      users = [],
      audit = [];
  bool loading = true;
  String? error;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    refresh();
    timer = Timer.periodic(
      const Duration(seconds: 12),
      (_) => refresh(silent: true),
    );
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> refresh({bool silent = false}) async {
    if (!silent && mounted) {
      setState(() {
        loading = true;
        error = null;
      });
    }
    try {
      final result = await Future.wait([
        widget.api.get('/admin/dashboard', widget.session),
        widget.api.getList('/incidents', widget.session),
        widget.api.getList('/admin/responders', widget.session),
        widget.api.getList('/admin/users?role=user', widget.session),
        widget.api.getList('/admin/resources', widget.session),
        widget.api.getList('/admin/audit', widget.session),
      ]);
      if (mounted) {
        setState(() {
          dashboard = result[0] as Map<String, dynamic>;
          incidents = result[1] as List;
          responders = result[2] as List;
          users = result[3] as List;
          resources = result[4] as List;
          audit = result[5] as List;
          loading = false;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString();
        });
      }
    }
  }

  Future<void> assign(
    Map<String, dynamic> incident, {
    bool reassign = false,
  }) async {
    try {
      final recommendationResult = await widget.api.get(
        '/admin/incidents/${incident['id']}/recommendations',
        widget.session,
      );
      final available =
          (recommendationResult['eligible_responders'] as List? ?? const [])
              .map((row) => Map<String, dynamic>.from(row as Map))
              .toList();
      if (!mounted) return;
      if (available.isEmpty) {
        setState(
          () => error = 'No available responder has a matching service capability. Incident remains visible as awaiting assignment.',
        );
        return;
      }
      final selected = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (dialogContext) => Dialog(
          insetPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 24,
          ),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: 520,
              maxHeight: MediaQuery.sizeOf(dialogContext).height * .78,
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Review responder recommendations',
                    style: Theme.of(dialogContext).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Choose an available responder. Scores support review; dispatch remains your decision.',
                    style: Theme.of(dialogContext).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 12),
                  Flexible(
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: available.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 8),
                      itemBuilder: (context, index) {
                        final row = available[index];
                        final isRecommended =
                            recommendationResult['recommended_responder_id'] ==
                            row['responder_id'];
                        final reasons = (row['reasons'] as List? ?? const [])
                            .map((reason) => reason.toString())
                            .toList();
                        return Card(
                          margin: EdgeInsets.zero,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(16),
                            onTap: () => Navigator.pop(dialogContext, row),
                            child: Padding(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    row['display_name'].toString(),
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleMedium
                                        ?.copyWith(fontWeight: FontWeight.w700),
                                  ),
                                  if (isRecommended) ...[
                                    const SizedBox(height: 6),
                                    const Chip(
                                      avatar: Icon(
                                        Icons.stars_outlined,
                                        size: 18,
                                      ),
                                      label: Text('Top recommendation'),
                                      visualDensity: VisualDensity.compact,
                                    ),
                                  ],
                                  const SizedBox(height: 4),
                                  Text(
                                    'Match score: ${row['score']}/100',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelLarge,
                                  ),
                                  if (reasons.isNotEmpty) ...[
                                    const SizedBox(height: 6),
                                    for (final reason in reasons)
                                      Padding(
                                        padding: const EdgeInsets.only(
                                          bottom: 3,
                                        ),
                                        child: Text('• $reason'),
                                      ),
                                  ],
                                  const SizedBox(height: 4),
                                  Text(
                                    'Tap to assign',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelMedium
                                        ?.copyWith(color: OpsColors.primary),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => Navigator.pop(dialogContext),
                      child: const Text('Cancel'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      if (selected == null) return;
      if (!mounted) return;
      final availableResources =
          (recommendationResult['compatible_resources'] as List? ?? const [])
              .map((row) => Map<String, dynamic>.from(row as Map))
              .where((row) => (row['available'] as num? ?? 0) > 0)
              .toList();
      String? resourceId;
      if (availableResources.isNotEmpty) {
        final chosenResource = await showDialog<String>(
          context: context,
          builder: (context) => SimpleDialog(
            title: const Text('Allocate a resource?'),
            children: [
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, ''),
                child: const Text('No resource'),
              ),
              for (final resource in availableResources)
                SimpleDialogOption(
                  onPressed: () =>
                      Navigator.pop(context, resource['id'] as String),
                  child: Text(
                    '${resource['name']} · ${resource['available']} available',
                  ),
                ),
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel assignment'),
              ),
            ],
          ),
        );
        if (chosenResource == null) return;
        resourceId = chosenResource.isEmpty ? null : chosenResource;
      }
      await widget.api.post(
        '/admin/incidents/${incident['id']}/${reassign ? 'reassign' : 'assign'}',
        widget.session,
        body: {
          'responder_id': selected['responder_id'],
          'resource_id': resourceId,
        },
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> createResponder() async {
    final values = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _FormDialog(
        title: 'Invite responder',
        fields: [
          ('Name', ''),
          ('Email', ''),
          ('Capabilities · comma separated', ''),
        ],
      ),
    );
    if (values == null) return;
    try {
      final invitation = await widget.api.post(
        '/admin/invitations/responders',
        widget.session,
        body: {
          'display_name': values['Name'],
          'email': values['Email'],
          'capabilities': (values['Capabilities · comma separated'] ?? '')
              .split(',')
              .map((s) => s.trim())
              .where((s) => s.isNotEmpty)
              .toList(),
        },
      );
      await refresh();
      if (!mounted) return;
      final activationUrl = invitation['activation_url'];
      if (activationUrl is String && activationUrl.isNotEmpty) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Responder invitation ready'),
            content: SelectableText(activationUrl),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Close'),
              ),
            ],
          ),
        );
      } else {
        final delivered = invitation['invitation_status'] == 'sent';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              delivered
                  ? 'Invitation email sent.'
                  : 'Responder invitation created.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> createResource() async {
    final values = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _FormDialog(
        title: 'Add operational resource',
        fields: [('Name', ''), ('Type', ''), ('Quantity', '1')],
      ),
    );
    if (values == null) return;
    try {
      await widget.api.post(
        '/admin/resources',
        widget.session,
        body: {
          'name': values['Name'],
          'kind': values['Type'],
          'quantity': int.tryParse(values['Quantity'] ?? '') ?? 0,
        },
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> editCapabilities(Map<String, dynamic> responder) async {
    final controller = TextEditingController(
      text: (responder['capabilities'] as List).join(', '),
    );
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Capabilities · ${responder['display_name']}'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Comma-separated service skills',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value == null) return;
    try {
      await widget.api.put(
        '/admin/responders/${responder['id']}/capabilities',
        widget.session,
        body: {
          'capabilities': value
              .split(',')
              .map((x) => x.trim())
              .where((x) => x.isNotEmpty)
              .toList(),
        },
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> editResource(Map<String, dynamic> resource) async {
    final values = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _FormDialog(
        title: 'Edit resource',
        fields: [
          ('Name', resource['name'].toString()),
          ('Type', resource['kind'].toString()),
          ('Quantity', resource['quantity'].toString()),
        ],
      ),
    );
    if (values == null) return;
    try {
      await widget.api.patch(
        '/admin/resources/${resource['id']}?active=${resource['active']}',
        widget.session,
        body: {
          'name': values['Name'],
          'kind': values['Type'],
          'quantity': int.tryParse(values['Quantity'] ?? '') ?? -1,
        },
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> setResourceActive(
    Map<String, dynamic> resource,
    bool active,
  ) async {
    try {
      await widget.api.patch(
        '/admin/resources/${resource['id']}?active=$active',
        widget.session,
        body: {
          'name': resource['name'],
          'kind': resource['kind'],
          'quantity': resource['quantity'],
        },
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> closeIncident(
    Map<String, dynamic> incident,
    String action,
  ) async {
    final isResolve = action == 'resolve';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(isResolve ? 'Resolve incident?' : 'Cancel incident?'),
        content: Text(
          isResolve
              ? 'This closes the incident and releases its current responder and allocated resource.'
              : 'This cancels the report and releases its current responder and allocated resource.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Back'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(isResolve ? 'Resolve' : 'Cancel incident'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await widget.api.post(
        '/admin/incidents/${incident['id']}/$action',
        widget.session,
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 7,
    child: Scaffold(
      appBar: AppBar(
        leading: const Padding(
          padding: EdgeInsets.all(8),
          child: CoordinationBrandMark(size: 48),
        ),
        title: const Text('Admin Portal'),
        actions: [
          IconButton(
            tooltip: 'Refresh data',
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: widget.onLogout,
            icon: const Icon(Icons.logout),
          ),
        ],
        bottom: const TabBar(
          isScrollable: true,
          tabs: [
            Tab(text: 'Dashboard'),
            Tab(text: 'Incidents'),
            Tab(text: 'Responders'),
            Tab(text: 'Users'),
            Tab(text: 'Resources'),
            Tab(text: 'Audit'),
            Tab(text: 'Copilot'),
          ],
        ),
      ),
      body: Column(
        children: [
          if (error != null)
            _FeedbackBox(text: error!, color: OpsColors.critical),
          if (loading) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: TabBarView(
              children: [
                _AdminDashboard(
                  data: dashboard,
                  incidents: incidents,
                  onIncident: (item) => assign(item),
                  api: widget.api,
                  session: widget.session,
                ),
                _AdminIncidents(
                  incidents: incidents,
                  api: widget.api,
                  session: widget.session,
                  onRefresh: refresh,
                  onAssign: (item) => assign(item),
                  onReassign: (item) => assign(item, reassign: true),
                  onResolve: (item) => closeIncident(item, 'resolve'),
                  onCancel: (item) => closeIncident(item, 'cancel'),
                ),
                _AdminResponders(
                  rows: responders,
                  onAdd: createResponder,
                  onEditCapabilities: editCapabilities,
                  onAvailability: (row, available) async {
                    try {
                      await widget.api.patch(
                        '/admin/responders/${row['id']}/availability',
                        widget.session,
                        body: {'available': available},
                      );
                      await refresh();
                    } catch (e) {
                      if (mounted) setState(() => error = e.toString());
                    }
                  },
                ),
                _AdminUsers(
                  rows: users,
                  onActiveChanged: (row, active) async {
                    try {
                      await widget.api.patch(
                        '/admin/users/${row['id']}/active?active=$active',
                        widget.session,
                      );
                      await refresh();
                    } catch (e) {
                      if (mounted) setState(() => error = e.toString());
                    }
                  },
                ),
                _AdminResources(
                  rows: resources,
                  onAdd: createResource,
                  onEdit: editResource,
                  onActiveChanged: setResourceActive,
                ),
                _AdminAudit(rows: audit),
                _AdminCopilot(api: widget.api, session: widget.session),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _AdminCopilot extends StatefulWidget {
  const _AdminCopilot({required this.api, required this.session});
  final ApiClient api;
  final ApiSession session;

  @override
  State<_AdminCopilot> createState() => _AdminCopilotState();
}

class _AdminCopilotState extends State<_AdminCopilot> {
  final question = TextEditingController();
  Map<String, dynamic>? response;
  String? error;
  bool loading = false;

  @override
  void dispose() {
    question.dispose();
    super.dispose();
  }

  Future<void> ask() async {
    if (question.text.trim().length < 2 || loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await widget.api.post(
        '/admin/copilot',
        widget.session,
        body: {'question': question.text.trim()},
      );
      if (mounted) setState(() => response = result);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'Operations Copilot',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 6),
      const Text(
        'Read-only answers from current coordination records. It cannot assign responders or change incident status.',
      ),
      const SizedBox(height: 14),
      TextField(
        controller: question,
        maxLength: 240,
        textInputAction: TextInputAction.send,
        onSubmitted: (_) => ask(),
        decoration: InputDecoration(
          labelText: 'Ask about operations',
          hintText: 'For example: Which reports are unassigned?',
          suffixIcon: IconButton(
            tooltip: 'Ask copilot',
            onPressed: loading ? null : ask,
            icon: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send),
          ),
        ),
      ),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final sample in const [
            'Unassigned reports',
            'Responder availability',
            'Resource utilization',
          ])
            ActionChip(
              label: Text(sample),
              onPressed: loading
                  ? null
                  : () {
                      question.text = sample;
                      ask();
                    },
            ),
        ],
      ),
      if (error != null) ...[
        const SizedBox(height: 12),
        _FeedbackBox(text: error!, color: OpsColors.critical),
      ],
      if (response != null) ...[
        const SizedBox(height: 14),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.fact_check_outlined),
                    const SizedBox(width: 8),
                    Text(
                      'Database answer · rules-based',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(response!['answer']?.toString() ?? 'No answer returned'),
                if ((response!['sources'] as List? ?? const []).isNotEmpty) ...[
                  const Divider(height: 24),
                  Text(
                    'Sources',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 6),
                  for (final source in response!['sources'] as List)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        source is Map && source['reference'] != null
                            ? '${source['reference']} · ${source['status'] ?? source['emergency_type'] ?? source['summary'] ?? ''}'
                            : source is Map && source['name'] != null
                            ? '${source['name']} · ${source['availability']} · ${(source['capabilities'] as List? ?? const []).join(', ')}'
                            : source.toString(),
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),
      ],
    ],
  );
}

class _AdminDashboard extends StatelessWidget {
  const _AdminDashboard({
    required this.data,
    required this.incidents,
    required this.onIncident,
    required this.api,
    required this.session,
  });
  final Map<String, dynamic> data;
  final List<dynamic> incidents;
  final ValueChanged<Map<String, dynamic>> onIncident;
  final ApiClient api;
  final ApiSession session;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'Live service snapshot',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          for (final key in const [
            'total_incidents',
            'active_incidents',
            'unassigned',
            'assigned',
            'in_progress',
            'resolved',
            'responders_available',
            'responders_busy',
            'responders_unavailable',
            'resources_allocated',
          ])
            SizedBox(
              width: 155,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${data[key] ?? '—'}',
                        style: const TextStyle(
                          fontSize: 25,
                          fontWeight: FontWeight.w800,
                          color: OpsColors.primaryDark,
                        ),
                      ),
                      Text(switch (key) {
                        'total_incidents' => 'Total reports',
                        'active_incidents' => 'Active',
                        'unassigned' => 'Awaiting assignment',
                        'assigned' => 'Assigned',
                        'in_progress' => 'In progress',
                        'resolved' => 'Resolved',
                        'responders_available' => 'Available responders',
                        'responders_busy' => 'Busy responders',
                        'responders_unavailable' => 'Unavailable responders',
                        _ => 'Resources allocated',
                      }, style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
      const SizedBox(height: 18),
      Text(
        'Awaiting assignment',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      for (final raw in incidents.where(
        (x) => (x as Map)['status'] == 'Unassigned',
      ))
        _IncidentCard(
          item: Map<String, dynamic>.from(raw as Map),
          compactLocation: true,
          onTap: () => _showAdminIncidentDetails(
            context,
            Map<String, dynamic>.from(raw),
            api: api,
            session: session,
          ),
          action: FilledButton.tonal(
            onPressed: () => onIncident(Map<String, dynamic>.from(raw)),
            child: const Text('Review responders'),
          ),
        ),
    ],
  );
}

class _AdminIncidents extends StatefulWidget {
  const _AdminIncidents({
    required this.incidents,
    required this.api,
    required this.session,
    required this.onRefresh,
    required this.onAssign,
    required this.onReassign,
    required this.onResolve,
    required this.onCancel,
  });
  final List<dynamic> incidents;
  final ApiClient api;
  final ApiSession session;
  final VoidCallback onRefresh;
  final ValueChanged<Map<String, dynamic>> onAssign, onReassign, onResolve;
  final ValueChanged<Map<String, dynamic>> onCancel;
  @override
  State<_AdminIncidents> createState() => _AdminIncidentsState();
}

class _AdminIncidentsState extends State<_AdminIncidents> {
  final search = TextEditingController();
  String filter = 'All';

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> get visibleIncidents => widget.incidents
      .map((raw) => Map<String, dynamic>.from(raw as Map))
      .where((item) {
        final status = item['status']?.toString() ?? '';
        final statusMatches = switch (filter) {
          'Active' => status != 'Resolved' && status != 'Cancelled',
          'Unassigned' => status == 'Unassigned',
          'Resolved' => status == 'Resolved',
          _ => true,
        };
        final needle = search.text.trim().toLowerCase();
        final searchMatches =
            needle.isEmpty ||
            [
              item['reference'],
              item['emergency_type'],
              item['description'],
              item['location_label'],
              item['priority'],
              item['status'],
              item['responder_name'],
            ].whereType<Object>().any(
              (value) => value.toString().toLowerCase().contains(needle),
            );
        return statusMatches && searchMatches;
      })
      .toList();

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      TextField(
        controller: search,
        onChanged: (_) => setState(() {}),
        decoration: InputDecoration(
          prefixIcon: const Icon(Icons.search),
          hintText: 'Search reports',
          suffixIcon: search.text.isEmpty
              ? null
              : IconButton(
                  tooltip: 'Clear search',
                  onPressed: () {
                    search.clear();
                    setState(() {});
                  },
                  icon: const Icon(Icons.close),
                ),
        ),
      ),
      const SizedBox(height: 8),
      Wrap(
        spacing: 6,
        children: [
          for (final choice in const [
            'All',
            'Active',
            'Unassigned',
            'Resolved',
          ])
            ChoiceChip(
              label: Text(choice),
              selected: filter == choice,
              onSelected: (_) => setState(() => filter = choice),
            ),
        ],
      ),
      Row(
        children: [
          Expanded(
            child: Text(
              '${visibleIncidents.length} ${visibleIncidents.length == 1 ? 'report' : 'reports'}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
          IconButton(
            tooltip: 'Refresh incidents',
            onPressed: widget.onRefresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      for (final item in visibleIncidents)
        Builder(
          builder: (context) {
            final status = item['status'];
            final terminal = ['Resolved', 'Cancelled'].contains(status);
            final canAssign = status == 'Unassigned';
            final canReassign = [
              'Assigned',
              'Accepted',
              'En Route',
              'On Scene',
            ].contains(status);
            return _IncidentCard(
              item: item,
              compactLocation: true,
              onTap: () => _showAdminIncidentDetails(
                context,
                item,
                api: widget.api,
                session: widget.session,
              ),
              action: Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  if (canAssign)
                    FilledButton.icon(
                      onPressed: () => widget.onAssign(item),
                      icon: const Icon(Icons.person_add_alt_1),
                      label: const Text('Assign responder'),
                    ),
                  if (canReassign)
                    OutlinedButton.icon(
                      onPressed: () => widget.onReassign(item),
                      icon: const Icon(Icons.swap_horiz),
                      label: const Text('Change responder'),
                    ),
                  if (!terminal)
                    PopupMenuButton<String>(
                      tooltip: 'More report actions',
                      onSelected: (value) {
                        if (value == 'resolve') widget.onResolve(item);
                        if (value == 'cancel') widget.onCancel(item);
                      },
                      itemBuilder: (context) => const [
                        PopupMenuItem(
                          value: 'resolve',
                          child: ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: Icon(Icons.check_circle_outline),
                            title: Text('Mark resolved'),
                          ),
                        ),
                        PopupMenuItem(
                          value: 'cancel',
                          child: ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: Icon(Icons.cancel_outlined),
                            title: Text('Cancel report'),
                          ),
                        ),
                      ],
                      child: const Padding(
                        padding: EdgeInsets.all(12),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text('More'),
                            SizedBox(width: 4),
                            Icon(Icons.expand_more),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      if (visibleIncidents.isEmpty)
        const _EmptyPanel(
          title: 'No matching reports',
          detail: 'Change the filters or search terms. New user requests will appear as they are received.',
        ),
    ],
  );
}

class _AdminResponders extends StatelessWidget {
  const _AdminResponders({
    required this.rows,
    required this.onAdd,
    required this.onAvailability,
    required this.onEditCapabilities,
  });
  final List<dynamic> rows;
  final VoidCallback onAdd;
  final void Function(Map<String, dynamic>, bool) onAvailability;
  final ValueChanged<Map<String, dynamic>> onEditCapabilities;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      FilledButton.icon(
        onPressed: onAdd,
        icon: const Icon(Icons.person_add_alt),
        label: const Text('Invite responder'),
      ),
      const SizedBox(height: 10),
      for (final raw in rows)
        Builder(
          builder: (context) {
            final row = Map<String, dynamic>.from(raw as Map);
            return Card(
              child: ListTile(
                leading: Icon(
                  row['available'] == true
                      ? Icons.person
                      : Icons.person_pin_circle,
                  color: row['available'] == true
                      ? OpsColors.success
                      : OpsColors.warning,
                ),
                title: Text(row['display_name'].toString()),
                subtitle: Text(
                  '${(row['capabilities'] as List).join(', ')}${row['active_incident_id'] == null ? '' : '\nAssigned incident: ${row['active_incident_id']}'}',
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      tooltip: 'Edit service capabilities',
                      onPressed: () => onEditCapabilities(row),
                      icon: const Icon(Icons.tune),
                    ),
                    Switch(
                      value: row['available'] == true,
                      onChanged: row['active_incident_id'] == null
                          ? (value) => onAvailability(row, value)
                          : null,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
    ],
  );
}

class _AdminUsers extends StatelessWidget {
  const _AdminUsers({required this.rows, required this.onActiveChanged});
  final List<dynamic> rows;
  final void Function(Map<String, dynamic>, bool) onActiveChanged;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text('User accounts', style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 10),
      if (rows.isEmpty)
        const _EmptyPanel(
          title: 'No user accounts',
          detail: 'User accounts appear here after registration.',
        ),
      for (final raw in rows)
        Builder(
          builder: (context) {
            final row = Map<String, dynamic>.from(raw as Map);
            return Card(
              child: ListTile(
                title: Text(row['display_name'].toString()),
                subtitle: Text(row['email'].toString()),
                trailing: Switch(
                  value: row['active'] == true,
                  onChanged: (active) => onActiveChanged(row, active),
                ),
              ),
            );
          },
        ),
    ],
  );
}

class _AdminResources extends StatelessWidget {
  const _AdminResources({
    required this.rows,
    required this.onAdd,
    required this.onEdit,
    required this.onActiveChanged,
  });
  final List<dynamic> rows;
  final VoidCallback onAdd;
  final ValueChanged<Map<String, dynamic>> onEdit;
  final void Function(Map<String, dynamic>, bool) onActiveChanged;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      FilledButton.icon(
        onPressed: onAdd,
        icon: const Icon(Icons.add_box_outlined),
        label: const Text('Add resource'),
      ),
      for (final raw in rows)
        Builder(
          builder: (context) {
            final row = Map<String, dynamic>.from(raw as Map);
            return Card(
              child: ListTile(
                leading: const Icon(Icons.inventory_2_outlined),
                title: Text(row['name'].toString()),
                subtitle: Text(
                  '${row['kind']} · ${row['available']} of ${row['quantity']} available',
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      tooltip: 'Edit resource',
                      onPressed: () => onEdit(row),
                      icon: const Icon(Icons.edit_outlined),
                    ),
                    Switch(
                      value: row['active'] == true,
                      onChanged: (active) => onActiveChanged(row, active),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
    ],
  );
}

class _AdminAudit extends StatelessWidget {
  const _AdminAudit({required this.rows});
  final List<dynamic> rows;
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        'Administrative audit history',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      for (final raw in rows)
        Builder(
          builder: (context) {
            final row = Map<String, dynamic>.from(raw as Map);
            return Card(
              child: ListTile(
                leading: const Icon(Icons.history),
                title: Text(row['action'].toString()),
                subtitle: Text(
                  '${row['entity_type']} ${row['entity_id']}\n${row['created_at']}',
                ),
              ),
            );
          },
        ),
    ],
  );
}

class ResponderPortal extends StatefulWidget {
  const ResponderPortal({
    super.key,
    required this.api,
    required this.session,
    required this.onLogout,
  });
  final ApiClient api;
  final ApiSession session;
  final VoidCallback onLogout;
  @override
  State<ResponderPortal> createState() => _ResponderPortalState();
}

class _ResponderPortalState extends State<ResponderPortal> {
  List<dynamic> tasks = [];
  bool loading = true;
  String? error;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    refresh();
    timer = Timer.periodic(
      const Duration(seconds: 12),
      (_) => refresh(silent: true),
    );
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> refresh({bool silent = false}) async {
    if (!silent && mounted) setState(() => loading = true);
    try {
      final rows = await widget.api.getList('/incidents', widget.session);
      if (mounted) {
        setState(() {
          tasks = rows;
          loading = false;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString();
        });
      }
    }
  }

  Future<void> setStatus(Map<String, dynamic> task) async {
    final next = switch (task['status']) {
      'Assigned' => 'Accepted',
      'Accepted' => 'En Route',
      'En Route' => 'On Scene',
      'On Scene' => 'Resolved',
      _ => null,
    };
    if (next == null) return;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Update status to $next?'),
        content: const Text(
          'This update will be shared with the user and admin portal.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Back'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await widget.api.post(
        '/responder/incidents/${task['id']}/status',
        widget.session,
        body: {'status': next},
      );
      await refresh();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> shareLocationOnce() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        throw const ApiException('Location services are turned off.');
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw const ApiException('Location permission was not granted.');
      }
      final fix = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 12),
        ),
      );
      await widget.api.put(
        '/responder/location',
        widget.session,
        body: {
          'latitude': fix.latitude,
          'longitude': fix.longitude,
          'accuracy_m': fix.accuracy,
          'captured_at': fix.timestamp.toUtc().toIso8601String(),
        },
      );
      if (mounted) {
        setState(() => error = null);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Location shared once for eligible responder recommendations.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> addOperationalUpdate(Map<String, dynamic> task) async {
    final controller = TextEditingController();
    final choice = await showDialog<(String, bool)>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add operational update'),
        content: TextField(
          controller: controller,
          maxLength: 1000,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'Update visible to the user and admin',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () =>
                Navigator.pop(context, (controller.text.trim(), true)),
            child: const Text('Improve with AI'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, (controller.text.trim(), false)),
            child: const Text('Send update'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (choice == null || choice.$1.isEmpty) return;
    try {
      var value = choice.$1;
      var originalMessage = '';
      var aiAssisted = false;
      if (choice.$2) {
        final result = await widget.api.post(
          '/responder/incidents/${task['id']}/rewrite',
          widget.session,
          body: {'note': value},
        );
        originalMessage = value;
        final suggestionController = TextEditingController(
          text: result['suggestion'] as String? ?? value,
        );
        if (!mounted) {
          suggestionController.dispose();
          return;
        }
        final accepted = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Review suggested update'),
            content: TextField(
              controller: suggestionController,
              maxLines: 4,
              maxLength: 1000,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Reject'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Use this text'),
              ),
            ],
          ),
        );
        if (accepted != true) {
          suggestionController.dispose();
          return;
        }
        value = suggestionController.text.trim();
        suggestionController.dispose();
        if (value.isEmpty) return;
        aiAssisted = result['outcome'] == 'validated_draft';
      }
      await widget.api.post(
        '/incidents/${task['id']}/updates',
        widget.session,
        body: {
          'message': value,
          if (aiAssisted) 'original_message': originalMessage,
          'ai_assisted': aiAssisted,
        },
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Update sent to the coordination record.'),
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: const Padding(
        padding: EdgeInsets.all(8),
        child: CoordinationBrandMark(size: 48),
      ),
      title: const Text('Responder Portal'),
      actions: [
        IconButton(
          tooltip: 'Notifications',
          onPressed: () =>
              _openNotificationInbox(context, widget.api, widget.session),
          icon: const Icon(Icons.notifications_outlined),
        ),
        IconButton(
          tooltip: 'Share current location once',
          onPressed: shareLocationOnce,
          icon: const Icon(Icons.my_location),
        ),
        IconButton(
          tooltip: 'Refresh assignments',
          onPressed: refresh,
          icon: const Icon(Icons.refresh),
        ),
        IconButton(
          tooltip: 'Sign out',
          onPressed: widget.onLogout,
          icon: const Icon(Icons.logout),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Assigned tasks', style: Theme.of(context).textTheme.titleLarge),
        if (loading) const LinearProgressIndicator(minHeight: 2),
        if (error != null)
          _FeedbackBox(text: error!, color: OpsColors.critical),
        if (tasks.isEmpty && !loading)
          const _EmptyPanel(
            title: 'No assigned tasks',
            detail: 'Assignments from an administrator will appear here.',
          ),
        for (final raw in tasks)
          Builder(
            builder: (context) {
              final task = Map<String, dynamic>.from(raw as Map);
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              task['emergency_type'].toString(),
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                          ),
                          _StatusChip(task['status'].toString()),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('${task['reference']} · ${task['priority']}'),
                      const SizedBox(height: 5),
                      Text(task['description'].toString()),
                      if (task['analysis'] is Map &&
                          (task['analysis'] as Map)['status'] == 'ready' &&
                          (task['analysis'] as Map)['result'] is Map)
                        _responderAnalysisPreview(
                          context,
                          (task['analysis'] as Map)['result'] as Map,
                          (task['analysis'] as Map)['provider']?.toString(),
                        ),
                      const SizedBox(height: 5),
                      Text(task['location_label'].toString()),
                      if (task['latitude'] != null && task['longitude'] != null)
                        Text(
                          'Coordinates: ${task['latitude']}, ${task['longitude']}',
                        ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        children: [
                          if ([
                            'Assigned',
                            'Accepted',
                            'En Route',
                            'On Scene',
                          ].contains(task['status']))
                            FilledButton(
                              onPressed: () => setStatus(task),
                              child: Text(switch (task['status']) {
                                'Assigned' => 'Accept task',
                                'Accepted' => 'En route',
                                'En Route' => 'On scene',
                                _ => 'Resolve task',
                              }),
                            ),
                          OutlinedButton.icon(
                            onPressed: () => _showUpdates(
                              context,
                              task,
                              widget.api,
                              widget.session,
                            ),
                            icon: const Icon(Icons.forum_outlined),
                            label: const Text('Updates'),
                          ),
                          if ([
                            'Assigned',
                            'Accepted',
                            'En Route',
                            'On Scene',
                          ].contains(task['status']))
                            OutlinedButton.icon(
                              onPressed: () => addOperationalUpdate(task),
                              icon: const Icon(Icons.add_comment_outlined),
                              label: const Text('Add update'),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
      ],
    ),
  );
}

class _IncidentCard extends StatelessWidget {
  const _IncidentCard({
    required this.item,
    this.action,
    this.onTap,
    this.compactLocation = false,
  });
  final Map<String, dynamic> item;
  final Widget? action;
  final VoidCallback? onTap;
  final bool compactLocation;
  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    item['emergency_type'].toString(),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                _StatusChip(item['status'].toString()),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              '${item['reference']} · ${item['priority']}',
              style: const TextStyle(
                color: OpsColors.primaryDark,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 5),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                _InfoTag(
                  icon: Icons.warning_amber_rounded,
                  label: 'Severity ${item['severity']}/5',
                ),
                _InfoTag(
                  icon: Icons.bolt_outlined,
                  label: 'Urgency ${item['urgency']}/5',
                ),
                _InfoTag(
                  icon: Icons.access_time,
                  label: _formatTimestamp(item['created_at']),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              item['description']?.toString().trim().isNotEmpty == true
                  ? item['description'].toString()
                  : 'No description provided',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.location_on_outlined, size: 18),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    compactLocation
                        ? _incidentListLocation(item['location_label'])
                        : item['location_label']
                                  ?.toString()
                                  .trim()
                                  .isNotEmpty ==
                              true
                        ? item['location_label'].toString()
                        : 'Location not provided',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            if (item['responder_name'] != null)
              Text('Responder: ${item['responder_name']}'),
            if (action != null)
              Padding(padding: const EdgeInsets.only(top: 10), child: action!),
          ],
        ),
      ),
    ),
  );
}

String _formatTimestamp(Object? value) {
  final parsed = DateTime.tryParse(value?.toString() ?? '');
  if (parsed == null) return 'Time unavailable';
  final local = parsed.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return '${local.day} ${months[local.month - 1]} $hour:$minute';
}

String _incidentListLocation(Object? value) {
  final label = value?.toString().trim() ?? '';
  if (label.isEmpty) return 'Location not provided';
  // Device GPS labels often embed coordinates; keep those for the details view.
  if (label.toLowerCase().contains('gps') ||
      RegExp(r'-?\d{1,3}\.\d{4,}').hasMatch(label)) {
    return 'GPS location shared · tap for coordinates';
  }
  return label;
}

class _InfoTag extends StatelessWidget {
  const _InfoTag({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(
        icon,
        size: 15,
        color: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
      const SizedBox(width: 4),
      Text(label, style: Theme.of(context).textTheme.bodySmall),
    ],
  );
}

Future<void> _showAdminIncidentDetails(
  BuildContext context,
  Map<String, dynamic> item, {
  required ApiClient api,
  required ApiSession session,
}) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  showDragHandle: true,
  builder: (context) => SafeArea(
    child: _AdminIncidentDetailsContent(item: item, api: api, session: session),
  ),
);

class _AdminIncidentDetailsContent extends StatefulWidget {
  const _AdminIncidentDetailsContent({
    required this.item,
    required this.api,
    required this.session,
  });
  final Map<String, dynamic> item;
  final ApiClient api;
  final ApiSession session;

  @override
  State<_AdminIncidentDetailsContent> createState() =>
      _AdminIncidentDetailsContentState();
}

class _AdminIncidentDetailsContentState
    extends State<_AdminIncidentDetailsContent> {
  late Future<Map<String, dynamic>> duplicates = widget.api.get(
    '/admin/incidents/${widget.item['id']}/duplicates',
    widget.session,
  );

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: EdgeInsets.fromLTRB(
      20,
      4,
      20,
      20 + MediaQuery.viewInsetsOf(context).bottom,
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          widget.item['emergency_type']?.toString() ?? 'Incident details',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 4),
        Wrap(
          spacing: 8,
          children: [
            Text(widget.item['reference']?.toString() ?? 'No reference'),
            _StatusChip(widget.item['status']?.toString() ?? 'Unknown'),
          ],
        ),
        const Divider(height: 24),
        _detailLine(context, 'Priority', widget.item['priority']?.toString()),
        _detailLine(
          context,
          'Severity',
          '${widget.item['severity'] ?? '—'} / 5',
        ),
        _detailLine(context, 'Urgency', '${widget.item['urgency'] ?? '—'} / 5'),
        _detailLine(
          context,
          'Reported',
          _formatTimestamp(widget.item['created_at']),
        ),
        _detailLine(
          context,
          'Description',
          widget.item['description']?.toString(),
        ),
        _detailLine(
          context,
          'Location',
          _incidentListLocation(widget.item['location_label'])
              .replaceFirst(' · tap for coordinates', ''),
        ),
        _detailLine(
          context,
          'Responder',
          widget.item['responder_name']?.toString(),
        ),
        if (widget.item['priority_reason'] != null)
          _detailLine(
            context,
            'Priority explanation',
            widget.item['priority_reason'].toString(),
          ),
        if (widget.item['latitude'] != null && widget.item['longitude'] != null)
          _detailLine(
            context,
            'GPS coordinates',
            '${widget.item['latitude']}, ${widget.item['longitude']} (±${(widget.item['accuracy_m'] as num?)?.round() ?? 'unknown'} m)',
          ),
        _analysisDetails(context, widget.item['analysis']),
        const Divider(height: 24),
        Text(
          'Possible duplicate reports',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 6),
        FutureBuilder<Map<String, dynamic>>(
          future: duplicates,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const LinearProgressIndicator();
            }
            if (snapshot.hasError) {
              return const Text('Duplicate check is unavailable.');
            }
            final candidates =
                snapshot.data?['candidates'] as List? ?? const [];
            if (candidates.isEmpty) {
              return const Text('No similar reports found for review.');
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'These are review suggestions only. Reports are never merged automatically.',
                ),
                for (final candidate in candidates)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.content_copy_outlined),
                    title: Text(
                      '${candidate['reference']} · ${candidate['status']}',
                    ),
                    subtitle: Text(candidate['explanation'].toString()),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}

Widget _analysisDetails(BuildContext context, Object? raw) {
  if (raw is! Map) {
    return const Card(
      child: ListTile(
        title: Text('Incident analysis'),
        subtitle: Text(
          'Not available yet. The report was saved independently.',
        ),
      ),
    );
  }
  final status = raw['status']?.toString() ?? 'pending';
  if (status != 'ready' || raw['result'] is! Map) {
    return Card(
      child: ListTile(
        title: const Text('Incident analysis'),
        subtitle: Text(
          status == 'pending' || status == 'processing'
              ? 'Analysis is processing. The report and deterministic dispatch priority remain available.'
              : 'Analysis is unavailable. Use the original report and deterministic priority.',
        ),
      ),
    );
  }
  final result = Map<String, dynamic>.from(raw['result'] as Map);
  final provider = raw['provider'] == 'rules_baseline'
      ? 'Rules-based text scan'
      : 'AI suggestion';
  final hazards = (result['hazards_to_verify'] as List? ?? const [])
      .map((item) => item is Map ? item['statement']?.toString() : null)
      .whereType<String>()
      .toList();
  final missing = (result['missing_information'] as List? ?? const [])
      .whereType<String>()
      .toList();
  return Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Decision support · $provider · human review required',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 6),
          Text(result['summary']?.toString() ?? 'No summary provided'),
          if (result['suggested_category'] != null) ...[
            const SizedBox(height: 6),
            Text(
              'Suggested category for review: ${result['suggested_category']}',
            ),
          ],
          if (hazards.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Reported terms to verify: ${hazards.join(', ')}'),
          ],
          if (missing.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text('Questions for review: ${missing.join(' · ')}'),
          ],
          if (result['confidence_note'] != null) ...[
            const SizedBox(height: 6),
            Text(
              result['confidence_note'].toString(),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (result['explanation'] != null) ...[
            const SizedBox(height: 6),
            Text(
              result['explanation'].toString(),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    ),
  );
}

Widget _responderAnalysisPreview(
  BuildContext context,
  Map result,
  String? provider,
) {
  final hazards = (result['hazards_to_verify'] as List? ?? const [])
      .map((item) => item is Map ? item['statement']?.toString() : null)
      .whereType<String>()
      .toList();
  final missing = (result['missing_information'] as List? ?? const [])
      .whereType<String>()
      .toList();
  return Card(
    color: OpsColors.surfaceRaised,
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            provider == 'rules_baseline'
                ? 'Report notes · rules-based scan'
                : 'Report notes · AI suggestion',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 4),
          Text(result['summary']?.toString() ?? 'No summary available'),
          if (hazards.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text('Verify from original report: ${hazards.join(', ')}'),
          ],
          if (missing.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text('Questions to check: ${missing.join(' · ')}'),
          ],
          const SizedBox(height: 4),
          Text(
            'Decision support only · check the caller’s original report.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    ),
  );
}

Widget _detailLine(BuildContext context, String label, String? value) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 2),
          Text(value?.trim().isNotEmpty == true ? value! : 'Not provided'),
        ],
      ),
    );

Future<void> _openNotificationInbox(
  BuildContext context,
  ApiClient api,
  ApiSession session,
) => Navigator.of(context).push(
  MaterialPageRoute<void>(
    builder: (_) => NotificationInboxPage(api: api, session: session),
  ),
);

class NotificationInboxPage extends StatefulWidget {
  const NotificationInboxPage({
    super.key,
    required this.api,
    required this.session,
  });
  final ApiClient api;
  final ApiSession session;

  @override
  State<NotificationInboxPage> createState() => _NotificationInboxPageState();
}

class _NotificationInboxPageState extends State<NotificationInboxPage> {
  List<dynamic> notifications = [];
  bool loading = true;
  String? error;

  Future<void> refresh() async {
    try {
      final rows = await widget.api.getList('/notifications', widget.session);
      if (mounted) {
        setState(() {
          notifications = rows;
          loading = false;
          error = null;
        });
      }
    } catch (exception) {
      if (mounted) {
        setState(() {
          loading = false;
          error = exception.toString();
        });
      }
    }
  }

  Future<void> markRead(String id) async {
    try {
      await widget.api.patch('/notifications/$id/read', widget.session);
      await refresh();
    } catch (exception) {
      if (mounted) setState(() => error = exception.toString());
    }
  }

  @override
  void initState() {
    super.initState();
    refresh();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Notifications'),
      actions: [
        TextButton(
          onPressed: notifications.any((item) => item['read'] != true)
              ? () async {
                  try {
                    await widget.api.patch(
                      '/notifications/read-all',
                      widget.session,
                    );
                    await refresh();
                  } catch (exception) {
                    if (mounted) setState(() => error = exception.toString());
                  }
                }
              : null,
          child: const Text('Mark all read'),
        ),
      ],
    ),
    body: loading
        ? const Center(child: CircularProgressIndicator())
        : error != null
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(error!, textAlign: TextAlign.center),
            ),
          )
        : notifications.isEmpty
        ? const Center(child: Text('You are all caught up.'))
        : ListView.separated(
            itemCount: notifications.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final item = Map<String, dynamic>.from(
                notifications[index] as Map,
              );
              final read = item['read'] == true;
              return ListTile(
                leading: Icon(
                  read
                      ? Icons.notifications_none
                      : Icons.notifications_active_outlined,
                ),
                title: Text(item['title']?.toString() ?? 'Update'),
                subtitle: Text(
                  '${item['message'] ?? ''}\n${item['created_at'] ?? ''}',
                ),
                isThreeLine: true,
                onTap: read ? null : () => markRead(item['id'].toString()),
              );
            },
          ),
  );
}

class _StatusChip extends StatelessWidget {
  const _StatusChip(this.value);
  final String value;
  @override
  Widget build(BuildContext context) => Chip(
    label: Text(value),
    visualDensity: VisualDensity.compact,
    backgroundColor: value == 'Resolved'
        ? OpsColors.primaryWash
        : value == 'Unassigned'
        ? OpsColors.accentWash
        : OpsColors.canvas,
  );
}

class _FeedbackBox extends StatelessWidget {
  const _FeedbackBox({required this.text, required this.color});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .09),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(text, style: TextStyle(color: color)),
  );
}

class _EmptyPanel extends StatelessWidget {
  const _EmptyPanel({required this.title, required this.detail});
  final String title, detail;
  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: const Icon(Icons.inbox_outlined),
      title: Text(title),
      subtitle: Text(detail),
    ),
  );
}

class _FormDialog extends StatefulWidget {
  const _FormDialog({required this.title, required this.fields});
  final String title;
  final List<(String, String)> fields;

  @override
  State<_FormDialog> createState() => _FormDialogState();
}

class _FormDialogState extends State<_FormDialog> {
  late final List<(String, TextEditingController)> _fields;

  @override
  void initState() {
    super.initState();
    _fields = [
      for (final field in widget.fields)
        (field.$1, TextEditingController(text: field.$2)),
    ];
  }

  @override
  void dispose() {
    for (final field in _fields) {
      field.$2.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.title),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final field in _fields)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: TextField(
                controller: field.$2,
                decoration: InputDecoration(labelText: field.$1),
              ),
            ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: () => Navigator.pop(context, {
          for (final field in _fields) field.$1: field.$2.text.trim(),
        }),
        child: const Text('Save'),
      ),
    ],
  );
}
