import React from 'react';
import PropTypes from 'prop-types';
import { translateString } from '../../utils/helpers/';
import { CircleIconButton, MaterialIcon } from '../_shared/';

export function OtherMediaDownloadLink(props) {
  return (
    <div className="download hidden-only-in-small">
      <a href={props.link + '?dl=1'} target="_blank" download={props.title} title={translateString('DOWNLOAD')} rel="noreferrer">
        <CircleIconButton type="span">
          <MaterialIcon type="arrow_downward" />
        </CircleIconButton>
        <span>{translateString('DOWNLOAD')}</span>
      </a>
    </div>
  );
}

OtherMediaDownloadLink.propTypes = {
  link: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
};
