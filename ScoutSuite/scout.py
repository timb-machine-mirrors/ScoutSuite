import asyncio
import copy
import os
import webbrowser

from concurrent.futures import ThreadPoolExecutor

from ScoutSuite.core.console import set_config_debug_level, print_info, print_exception
from ScoutSuite.core.exceptions import RuleExceptions
from ScoutSuite.core.processingengine import ProcessingEngine
from ScoutSuite.core.ruleset import Ruleset
from ScoutSuite.output.html import ScoutReport
from ScoutSuite.providers import get_provider
from ScoutSuite.providers.base.authentication_strategy_factory import get_authentication_strategy


def run(provider,
        profile,
        user_account, service_account,
        cli, msi, service_principal, file_auth, tenant_id, subscription_id,
        client_id, client_secret,
        username, password,
        project_id, folder_id, organization_id, all_projects,
        report_name, report_dir,
        timestamp,
        services, skipped_services,
        thread_config,  # TODO deprecate
        max_workers,
        regions,
        fetch_local, update,
        ip_ranges, ip_ranges_name_key,
        ruleset, exceptions,
        force_write,
        debug,
        no_browser):
    """
    Run a scout job in an async event loop.
    """

    loop = asyncio.get_event_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=max_workers))
    loop.run_until_complete(_run(**locals()))  # pass through all the parameters
    loop.close()


# noinspection PyBroadException
async def _run(provider,
               profile,
               user_account, service_account,
               cli, msi, service_principal, file_auth, tenant_id, subscription_id,
               client_id, client_secret,
               username, password,
               project_id, folder_id, organization_id, all_projects,
               report_name, report_dir,
               timestamp,
               services, skipped_services,
               thread_config,  # TODO deprecate
               regions,
               fetch_local, update,
               ip_ranges, ip_ranges_name_key,
               ruleset, exceptions,
               force_write,
               debug,
               no_browser,
               **kwargs):
    """
    Run a scout job.
    """

    # Configure the debug level
    set_config_debug_level(debug)

    print_info('Launching Scout')

    print_info('Authenticating to cloud provider')
    auth_strategy = get_authentication_strategy(provider)
    try:
        credentials = auth_strategy.authenticate(profile=profile,
                                                 user_account=user_account,
                                                 service_account=service_account,
                                                 cli=cli,
                                                 msi=msi,
                                                 service_principal=service_principal,
                                                 file_auth=file_auth,
                                                 tenant_id=tenant_id,
                                                 subscription_id=subscription_id,
                                                 client_id=client_id,
                                                 client_secret=client_secret,
                                                 username=username,
                                                 password=password)

        if not credentials:
            return 401
    except Exception as e:
        print_exception('Authentication failure: {}'.format(e))
        return 401

    # Create a cloud provider object
    cloud_provider = get_provider(provider=provider,
                                  profile=profile,
                                  project_id=project_id,
                                  folder_id=folder_id,
                                  organization_id=organization_id,
                                  all_projects=all_projects,
                                  report_dir=report_dir,
                                  timestamp=timestamp,
                                  services=services,
                                  skipped_services=skipped_services,
                                  thread_config=thread_config,
                                  credentials=credentials)

    # Create a new report
    report_name = report_name if report_name else cloud_provider.get_report_name()
    report = ScoutReport(cloud_provider.provider_code,
                         report_name,
                         report_dir,
                         timestamp)

    # Complete run, including pulling data from provider
    if not fetch_local:

        # Fetch data from provider APIs
        try:
            print_info('Gathering data from APIs')
            await cloud_provider.fetch(regions=regions)
        except KeyboardInterrupt:
            print_info('\nCancelled by user')
            return 130

        # Update means we reload the whole config and overwrite part of it
        if update:
            print_info('Updating existing data')
            current_run_services = copy.deepcopy(cloud_provider.services)
            last_run_dict = report.jsrw.load_from_file('RESULTS')
            cloud_provider.services = last_run_dict['services']
            for service in cloud_provider.service_list:
                cloud_provider.services[service] = current_run_services[service]

    # Partial run, using pre-pulled data
    else:
        print_info('Using local data')
        # Reload to flatten everything into a python dictionary
        last_run_dict = report.jsrw.load_from_file('RESULTS')
        for key in last_run_dict:
            setattr(cloud_provider, key, last_run_dict[key])

    # Pre processing
    cloud_provider.preprocessing(
        ip_ranges, ip_ranges_name_key)

    # Analyze config
    print_info('Running rule engine')
    finding_rules = Ruleset(cloud_provider=cloud_provider.provider_code,
                            environment_name=cloud_provider.environment,
                            filename=ruleset,
                            ip_ranges=ip_ranges,
                            account_id=cloud_provider.account_id)
    processing_engine = ProcessingEngine(finding_rules)
    processing_engine.run(cloud_provider)

    # Create display filters
    print_info('Applying display filters')
    filter_rules = Ruleset(cloud_provider=cloud_provider.provider_code,
                           environment_name=cloud_provider.environment,
                           rule_type='filters',
                           account_id=cloud_provider.account_id)
    processing_engine = ProcessingEngine(filter_rules)
    processing_engine.run(cloud_provider)

    # Handle exceptions
    if exceptions:
        print_info('Applying exceptions')
        try:
            exceptions = RuleExceptions(
                profile, exceptions)
            exceptions.process(cloud_provider)
            exceptions = exceptions.exceptions
        except Exception as e:
            print_exception('Failed to load exceptions: {}'.format(e))
            exceptions = {}
    else:
        exceptions = {}

    # Finalize
    cloud_provider.postprocessing(report.current_time, finding_rules)

    # Save config and create HTML report
    html_report_path = report.save(
        cloud_provider, exceptions, force_write, debug)

    # Open the report by default
    if not no_browser:
        print_info('Opening the HTML report')
        url = 'file://%s' % os.path.abspath(html_report_path)
        webbrowser.open(url, new=2)

    return 0