"""
XBlock to allow for video playback from Amazon Media Services

Built using documentation from: http://amp.azure.net/libs/amp/latest/docs/index.html
"""

import logging
import jwt
import base64
import time

from uuid import uuid4

from .utils import _

from xblock.core import String, Scope, List, XBlock
from xblock.fields import Boolean, Float, Integer, Dict
from xblock.fragment import Fragment
from xblock.validation import ValidationMessage

from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin

log = logging.getLogger(__name__)


@XBlock.needs('i18n')
class AMSXBlock(StudioEditableXBlockMixin, XBlock):
    """
    The xBlock to play videos from Azure Media Services
    """

    display_name = String(
        display_name=_("Display Name"),
        help=_(
            "Enter the name that students see for this component. "
            "Analytics reports may also use the display name to identify this component."
        ),
        scope=Scope.settings,
        default=_("Azure Media Services Video Player"),
    )
    video_url = String(
        display_name=_("Video Url"),
        help=_(
            "Enter the URL to your published video on Azure Media Services"
        ),
        default="",
        scope=Scope.settings
    )
    # Ultimately this should come via some secure means, but this is OK for a PoC
    verification_key = String(
        display_name=_("Verification Key"),
        help=_(
            "Enter the Base64 encoded Verification Key from your Azure Management Portal"
        ),
        default="",
        scope=Scope.settings
    )
    protection_type = String(
        display_name=_("Protection Type"),
        help=_(
            "This can be either blank (meaning unprotected), 'AES', or 'PlayReady'"
        ),
        default="",
        scope=Scope.settings
    )
    captions = List(
        display_name=_("Captions"),
        help=_("A list of caption definitions"),
        scope=Scope.settings
    )
    transcript_url = String(
        display_name=_("Transcript URL"),
        help=_("A transcript URL"),
        scope=Scope.settings
    )

    # These are what become visible in the Mixin editor
    editable_fields = (
        'display_name', 'video_url', 'verification_key', 'protection_type', 'captions',
        'transcript_url'
    )

    def _get_context_for_template(self):
        """
        Add parameters for the student view
        """
        context = {
            "video_url": self.video_url,
            "protection_type": self.protection_type,
            "captions": self.captions,
            "transcript_url": self.transcript_url,
            # this is only for the HTML DOM id of the player element, it can change
            # we make a random one for now so that multiple players can live on the same page
            "player_dom_id": uuid4().hex
        }

        if self.protection_type:
            # Create a JWT authentication token to have the Azure Media Services
            # create necessary DRM licenses

            secret = base64.b64decode(self.verification_key)

            payload = {
                # @TODO change claims to something sensible
                # Should the claims be fixed or configurable?
                u"iss": u"http://www.mpd-test.com/",
                u"aud": u"urn:mpd-test",
                u"exp": int(time.time()) + 600,
            }

            auth_token = jwt.encode(
                payload,
                secret,
                algorithm='HS256'
            )

            context.update({
                "auth_token": auth_token,
            })

        return context

    def student_view(self, context):
        """
        XBlock student view of this component.

        Arguments:
            context (dict): XBlock context

        Returns:
            xblock.fragment.Fragment: XBlock HTML fragment
        """
        fragment = Fragment()
        loader = ResourceLoader(__name__)
        context.update(self._get_context_for_template())
        fragment.add_content(loader.render_mako_template('/templates/player.html', context))

        '''
        @TODO: Note: DO NOT USE the "latest" folder in production. Replace "latest" with a version number like "1.0.0"
        EX:<script src="//amp.azure.net/libs/amp/1.0.0/azuremediaplayer.min.js"></script>
        Azure Media Player versions can be queried from //aka.ms/ampchangelog
        '''
        fragment.add_css_url('//amp.azure.net/libs/amp/latest/skins/amp-default/azuremediaplayer.min.css')
        fragment.add_javascript_url('//amp.azure.net/libs/amp/latest/azuremediaplayer.min.js')

        fragment.add_javascript(
            loader.render_mako_template(
                '/static/js/player.js',
                context
            )
        )

        fragment.add_css_url(self.runtime.local_resource_url(self, 'public/css/player.css'))

        # NOTE: The Azure Media Player JS file includes the VTT JavaScript library, so we don't
        # actually need to include our local copy of public/js/vendor/vtt.js. In fact, if we do
        # the overlay subtitles stop working


        # @TODO: Make sure all fields are well structured/formatted, if it is not correct, then
        # print out an error msg in view rather than just silently failing

        fragment.initialize_js('AzureMediaServicesBlock')
        return fragment

    @XBlock.json_handler
    def publish_event(self, data, suffix=''):
        try:
            event_type = data.pop('event_type')
        except KeyError as e:
            return {'result': 'error', 'message': 'Missing event_type in JSON data'}

        data['video_url'] = self.video_url
        data['user_id'] = self.scope_ids.user_id

        self.runtime.publish(self, event_type, data)
        return {'result':'success'}
