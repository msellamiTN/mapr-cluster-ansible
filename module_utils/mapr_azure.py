from msrestazure.azure_active_directory import ServicePrincipalCredentials, UserPassCredentials

from ansible.module_utils.mapr_base import MapRBase


class AzureException(Exception):
    pass


class MapRAzure(MapRBase):
    SERVICE_PRINCIPAL = "service_principal"
    USER_PASSWORD = "user_password"

    def __init__(self, this_module):
        self.this_module = this_module
        self.subscription_id = this_module.params.get("subscription_id")
        self.auth_type = this_module.params.get("auth_type").lower()
        self.client_id = this_module.params.get("client_id")
        self.secret = this_module.params.get("secret")
        self.tenant = this_module.params.get("tenant")
        self.username = this_module.params.get("username")
        self.password = this_module.params.get("password")
        self.resource_group = this_module.params.get("resource_group")

    def _get_credentials(self):
        if self.auth_type == MapRAzure.SERVICE_PRINCIPAL:
            credentials = ServicePrincipalCredentials(self.client_id,
                self.secret, tenant=self.tenant)
        else:
            credentials = UserPassCredentials(self.username, self.password)

        return credentials

    def _validate_credentials(self):
        if self.auth_type == MapRAzure.SERVICE_PRINCIPAL:
            if len(self.client_id) == 0:
                raise AzureException("client_id must be set when "
                    "using service_principal auth type")
            if len(self.secret) == 0:
                raise AzureException("secret must be set when using "
                    "service_principal auth type")
            if len(self.tenant) == 0:
                raise AzureException("tenant must be set when using "
                    "service_principal auth type")
            if len(self.subscription_id) == 0:
                raise AzureException("subscription_id must be set when using "
                                 "service_principal auth type")
        elif self.auth_type == MapRAzure.USER_PASSWORD:
            if len(self.username) == 0:
                raise AzureException("username must be set when "
                    "using user_password auth type")
            if len(self.password) == 0:
                raise AzureException("password must be set when "
                    "using user_password auth type")
        else:
            raise AzureException("auth_type must be service_principal"
                    " or user_password")
