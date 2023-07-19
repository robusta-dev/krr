from kubernetes import client
import six

from kubernetes.client.exceptions import (  # noqa: F401
    ApiTypeError,

)


class RolloutAppsV1Api(client.AppsV1Api):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list_rollout_for_all_namespaces(self, **kwargs):  # noqa: E501
        """list_rollout_for_all_namespaces  # noqa: E501

        list or watch objects of kind Deployment  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.list_rollout_for_all_namespaces(async_req=True)
        >>> result = thread.get()

        :param async_req bool: execute request asynchronously
        :param bool allow_watch_bookmarks: allowWatchBookmarks requests watch events with type \"BOOKMARK\". Servers that do not implement bookmarks may ignore this flag and bookmarks are sent at the server's discretion. Clients should not assume bookmarks are returned at any specific interval, nor may they assume the server will send any BOOKMARK event during a session. If this is not a watch, this field is ignored.
        :param str _continue: The continue option should be set when retrieving more results from the server. Since this value is server defined, clients may only use the continue value from a previous query result with identical query parameters (except for the value of continue) and the server may reject a continue value it does not recognize. If the specified continue value is no longer valid whether due to expiration (generally five to fifteen minutes) or a configuration change on the server, the server will respond with a 410 ResourceExpired error together with a continue token. If the client needs a consistent list, it must restart their list without the continue field. Otherwise, the client may send another list request with the token received with the 410 error, the server will respond with a list starting from the next key, but from the latest snapshot, which is inconsistent from the previous list results - objects that are created, modified, or deleted after the first list request will be included in the response, as long as their keys are after the \"next key\".  This field is not supported when watch is true. Clients may start a watch from the last resourceVersion value returned by the server and not miss any modifications.
        :param str field_selector: A selector to restrict the list of returned objects by their fields. Defaults to everything.
        :param str label_selector: A selector to restrict the list of returned objects by their labels. Defaults to everything.
        :param int limit: limit is a maximum number of responses to return for a list call. If more items exist, the server will set the `continue` field on the list metadata to a value that can be used with the same initial query to retrieve the next set of results. Setting a limit may return fewer than the requested amount of items (up to zero items) in the event all requested objects are filtered out and clients should only use the presence of the continue field to determine whether more results are available. Servers may choose not to support the limit argument and will return all of the available results. If limit is specified and the continue field is empty, clients may assume that no more results are available. This field is not supported if watch is true.  The server guarantees that the objects returned when using continue will be identical to issuing a single list call without a limit - that is, no objects created, modified, or deleted after the first request is issued will be included in any subsequent continued requests. This is sometimes referred to as a consistent snapshot, and ensures that a client that is using limit to receive smaller chunks of a very large result can ensure they see all possible objects. If objects are updated during a chunked list the version of the object that was present at the time the first list result was calculated is returned.
        :param str pretty: If 'true', then the output is pretty printed.
        :param str resource_version: resourceVersion sets a constraint on what resource versions a request may be served from. See https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions for details.  Defaults to unset
        :param str resource_version_match: resourceVersionMatch determines how resourceVersion is applied to list calls. It is highly recommended that resourceVersionMatch be set for list calls where resourceVersion is set See https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions for details.  Defaults to unset
        :param int timeout_seconds: Timeout for the list/watch call. This limits the duration of the call, regardless of any activity or inactivity.
        :param bool watch: Watch for changes to the described resources and return them as a stream of add, update, and remove notifications. Specify resourceVersion.
        :param _preload_content: if False, the urllib3.HTTPResponse object will
                                 be returned without reading/decoding response
                                 data. Default is True.
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        :return: V1RolloutList
                 If the method is called asynchronously,
                 returns the request thread.
        """
        kwargs['_return_http_data_only'] = True
        return self.list_rollout_for_all_namespaces_with_http_info(**kwargs)  # noqa: E501

    def list_rollout_for_all_namespaces_with_http_info(self, **kwargs):  # noqa: E501
        """list_rollout_for_all_namespaces  # noqa: E501

        list or watch objects of kind Deployment  # noqa: E501
        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please pass async_req=True
        >>> thread = api.list_deployment_for_all_namespaces_with_http_info(async_req=True)
        >>> result = thread.get()

        :param async_req bool: execute request asynchronously
        :param bool allow_watch_bookmarks: allowWatchBookmarks requests watch events with type \"BOOKMARK\". Servers that do not implement bookmarks may ignore this flag and bookmarks are sent at the server's discretion. Clients should not assume bookmarks are returned at any specific interval, nor may they assume the server will send any BOOKMARK event during a session. If this is not a watch, this field is ignored.
        :param str _continue: The continue option should be set when retrieving more results from the server. Since this value is server defined, clients may only use the continue value from a previous query result with identical query parameters (except for the value of continue) and the server may reject a continue value it does not recognize. If the specified continue value is no longer valid whether due to expiration (generally five to fifteen minutes) or a configuration change on the server, the server will respond with a 410 ResourceExpired error together with a continue token. If the client needs a consistent list, it must restart their list without the continue field. Otherwise, the client may send another list request with the token received with the 410 error, the server will respond with a list starting from the next key, but from the latest snapshot, which is inconsistent from the previous list results - objects that are created, modified, or deleted after the first list request will be included in the response, as long as their keys are after the \"next key\".  This field is not supported when watch is true. Clients may start a watch from the last resourceVersion value returned by the server and not miss any modifications.
        :param str field_selector: A selector to restrict the list of returned objects by their fields. Defaults to everything.
        :param str label_selector: A selector to restrict the list of returned objects by their labels. Defaults to everything.
        :param int limit: limit is a maximum number of responses to return for a list call. If more items exist, the server will set the `continue` field on the list metadata to a value that can be used with the same initial query to retrieve the next set of results. Setting a limit may return fewer than the requested amount of items (up to zero items) in the event all requested objects are filtered out and clients should only use the presence of the continue field to determine whether more results are available. Servers may choose not to support the limit argument and will return all of the available results. If limit is specified and the continue field is empty, clients may assume that no more results are available. This field is not supported if watch is true.  The server guarantees that the objects returned when using continue will be identical to issuing a single list call without a limit - that is, no objects created, modified, or deleted after the first request is issued will be included in any subsequent continued requests. This is sometimes referred to as a consistent snapshot, and ensures that a client that is using limit to receive smaller chunks of a very large result can ensure they see all possible objects. If objects are updated during a chunked list the version of the object that was present at the time the first list result was calculated is returned.
        :param str pretty: If 'true', then the output is pretty printed.
        :param str resource_version: resourceVersion sets a constraint on what resource versions a request may be served from. See https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions for details.  Defaults to unset
        :param str resource_version_match: resourceVersionMatch determines how resourceVersion is applied to list calls. It is highly recommended that resourceVersionMatch be set for list calls where resourceVersion is set See https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions for details.  Defaults to unset
        :param int timeout_seconds: Timeout for the list/watch call. This limits the duration of the call, regardless of any activity or inactivity.
        :param bool watch: Watch for changes to the described resources and return them as a stream of add, update, and remove notifications. Specify resourceVersion.
        :param _return_http_data_only: response data without head status code
                                       and headers
        :param _preload_content: if False, the urllib3.HTTPResponse object will
                                 be returned without reading/decoding response
                                 data. Default is True.
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        :return: tuple(V1DeploymentList, status_code(int), headers(HTTPHeaderDict))
                 If the method is called asynchronously,
                 returns the request thread.
        """

        local_var_params = locals()

        all_params = [
            'allow_watch_bookmarks',
            '_continue',
            'field_selector',
            'label_selector',
            'limit',
            'pretty',
            'resource_version',
            'resource_version_match',
            'timeout_seconds',
            'watch'
        ]
        all_params.extend(
            [
                'async_req',
                '_return_http_data_only',
                '_preload_content',
                '_request_timeout'
            ]
        )

        for key, val in six.iteritems(local_var_params['kwargs']):
            if key not in all_params:
                raise ApiTypeError(
                    "Got an unexpected keyword argument '%s'"
                    " to method list_deployment_for_all_namespaces" % key
                )
            local_var_params[key] = val
        del local_var_params['kwargs']

        collection_formats = {}

        path_params = {}

        query_params = []
        if 'allow_watch_bookmarks' in local_var_params and local_var_params['allow_watch_bookmarks'] is not None:  # noqa: E501
            query_params.append(('allowWatchBookmarks', local_var_params['allow_watch_bookmarks']))  # noqa: E501
        if '_continue' in local_var_params and local_var_params['_continue'] is not None:  # noqa: E501
            query_params.append(('continue', local_var_params['_continue']))  # noqa: E501
        if 'field_selector' in local_var_params and local_var_params['field_selector'] is not None:  # noqa: E501
            query_params.append(('fieldSelector', local_var_params['field_selector']))  # noqa: E501
        if 'label_selector' in local_var_params and local_var_params['label_selector'] is not None:  # noqa: E501
            query_params.append(('labelSelector', local_var_params['label_selector']))  # noqa: E501
        if 'limit' in local_var_params and local_var_params['limit'] is not None:  # noqa: E501
            query_params.append(('limit', local_var_params['limit']))  # noqa: E501
        if 'pretty' in local_var_params and local_var_params['pretty'] is not None:  # noqa: E501
            query_params.append(('pretty', local_var_params['pretty']))  # noqa: E501
        if 'resource_version' in local_var_params and local_var_params['resource_version'] is not None:  # noqa: E501
            query_params.append(('resourceVersion', local_var_params['resource_version']))  # noqa: E501
        if 'resource_version_match' in local_var_params and local_var_params['resource_version_match'] is not None:  # noqa: E501
            query_params.append(('resourceVersionMatch', local_var_params['resource_version_match']))  # noqa: E501
        if 'timeout_seconds' in local_var_params and local_var_params['timeout_seconds'] is not None:  # noqa: E501
            query_params.append(('timeoutSeconds', local_var_params['timeout_seconds']))  # noqa: E501
        if 'watch' in local_var_params and local_var_params['watch'] is not None:  # noqa: E501
            query_params.append(('watch', local_var_params['watch']))  # noqa: E501

        header_params = {}

        form_params = []
        local_var_files = {}

        body_params = None
        # HTTP header `Accept`
        header_params['Accept'] = self.api_client.select_header_accept(
            ['application/json', 'application/yaml', 'application/vnd.kubernetes.protobuf', 'application/json;stream=watch', 'application/vnd.kubernetes.protobuf;stream=watch'])  # noqa: E501

        # Authentication setting
        auth_settings = ['BearerToken']  # noqa: E501

        return self.api_client.call_api(
            '/apis/argoproj.io/v1alpha1/rollouts', 'GET',
            path_params,
            query_params,
            header_params,
            body=body_params,
            post_params=form_params,
            files=local_var_files,
            response_type='V1DeploymentList',  # noqa: E501
            auth_settings=auth_settings,
            async_req=local_var_params.get('async_req'),
            _return_http_data_only=local_var_params.get('_return_http_data_only'),  # noqa: E501
            _preload_content=local_var_params.get('_preload_content', True),
            _request_timeout=local_var_params.get('_request_timeout'),
            collection_formats=collection_formats)
