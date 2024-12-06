import json
import os
from functools import wraps

from flask import abort, request
from flask_login import current_user

from configs import dify_config
from controllers.console.workspace.error import AccountNotInitializedError
from models.model import DifySetup
from services.feature_service import FeatureService, LicenseStatus
from services.operation_service import OperationService

from .error import NotInitValidateError, NotSetupError, UnauthorizedAndForceLogout


def account_initialization_required(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        # check account initialization
        account = current_user

        if account.status == "uninitialized":
            raise AccountNotInitializedError()

        return view(*args, **kwargs)

    return decorated


def only_edition_cloud(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        if dify_config.EDITION != "CLOUD":
            abort(404)

        return view(*args, **kwargs)

    return decorated


def only_edition_self_hosted(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        if dify_config.EDITION != "SELF_HOSTED":
            abort(404)

        return view(*args, **kwargs)

    return decorated


def cloud_edition_billing_resource_check(resource: str):
    def interceptor(view):
        @wraps(view)
        def decorated(*args, **kwargs):
            # Permitir todos os recursos sem verificar limites
            return view(*args, **kwargs)
        return decorated
    return interceptor


def cloud_edition_billing_knowledge_limit_check(resource: str):
    def interceptor(view):
        @wraps(view)
        def decorated(*args, **kwargs):
            features = FeatureService.get_features(current_user.current_tenant_id)
            if features.billing.enabled:
                if resource == "add_segment":
                    if features.billing.subscription.plan == "sandbox":
                        abort(
                            403,
                            "To unlock this feature and elevate your Dify experience, please upgrade to a paid plan.",
                        )
                else:
                    return view(*args, **kwargs)

            return view(*args, **kwargs)

        return decorated

    return interceptor


def cloud_utm_record(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        try:
            features = FeatureService.get_features(current_user.current_tenant_id)

            if features.billing.enabled:
                utm_info = request.cookies.get("utm_info")

                if utm_info:
                    utm_info = json.loads(utm_info)
                    OperationService.record_utm(current_user.current_tenant_id, utm_info)
        except Exception as e:
            pass
        return view(*args, **kwargs)

    return decorated


def setup_required(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        # check setup
        if dify_config.EDITION == "SELF_HOSTED" and os.environ.get("INIT_PASSWORD") and not DifySetup.query.first():
            raise NotInitValidateError()
        elif dify_config.EDITION == "SELF_HOSTED" and not DifySetup.query.first():
            raise NotSetupError()

        return view(*args, **kwargs)

    return decorated


def enterprise_license_required(view):
    @wraps(view)
    def decorated(*args, **kwargs):
        settings = FeatureService.get_system_features()
        if settings.license.status in [LicenseStatus.INACTIVE, LicenseStatus.EXPIRED, LicenseStatus.LOST]:
            raise UnauthorizedAndForceLogout("Your license is invalid. Please contact your administrator.")

        return view(*args, **kwargs)

    return decorated
