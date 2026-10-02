import type { ComponentType } from "react";
import type { CardViewModel } from "../viewmodels/types";
import type { CardBodyContent } from "../../components/types";

export type CardPresenterProps = {
  card: CardViewModel;
  /** Feature-specific content slice selected by composition — never ClinicalContentViewModel. */
  content?: CardBodyContent | null;
  onAcknowledge?: (objectId: string) => void;
};

export type CardPresenter = ComponentType<CardPresenterProps>;
