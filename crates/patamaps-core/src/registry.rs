//! Registered relation data. Registration never admits a consumer generation.
use crate::{
    CheckError, CheckedGraph, ImportedLegacyRelationPack, Issue, import_legacy_relation_pack,
};
use patamaps_contracts::{GraphDocument, Relation, RelationLaw, RelationPack, parse};
use serde_json::Value;
use std::collections::HashSet;

/// Registration preserves pack and relation order. Each mutation validates the
/// complete proposed registry before replacing the previous state.
#[derive(Debug, Clone)]
pub struct RelationRegistry {
    packs: Vec<RelationPack>,
    legacy: Option<Vec<ImportedLegacyRelationPack>>,
}

impl RelationRegistry {
    pub fn new(packs: impl IntoIterator<Item = RelationPack>) -> Result<Self, CheckError> {
        let mut registry = Self {
            packs: Vec::new(),
            legacy: None,
        };
        for pack in packs {
            registry.register_pack(pack)?;
        }
        Ok(registry)
    }

    pub fn with_core() -> Result<Self, CheckError> {
        Self::new([parse(include_bytes!("../../../relation-packs/core.json"))?])
    }

    /// Interpret the pinned legacy core's definitions with their original pack
    /// identity. The original data and legacy digest remain separately available.
    pub fn with_legacy_core() -> Result<Self, CheckError> {
        Self::from_legacy_packs([parse(include_bytes!("legacy_core.json"))?])
    }

    /// Construct an immutable read-only snapshot of portable legacy 1.0/2.0
    /// documents. Empty 1.0 kind lists retain their original meaning; executable
    /// dependencies bind to original addresses, never rewritten native views.
    /// This does not reproduce mutable or unchecked legacy JS registration.
    pub fn from_legacy_packs(packs: impl IntoIterator<Item = Value>) -> Result<Self, CheckError> {
        let mut registry = Self {
            packs: Vec::new(),
            legacy: Some(Vec::new()),
        };
        let mut relations = HashSet::new();
        for document in packs {
            let subject = document
                .get("id")
                .and_then(Value::as_str)
                .unwrap_or("$")
                .to_owned();
            let imported = import_legacy_relation_pack(document).map_err(|error| {
                CheckError(vec![Issue::error(&error.code, error.message, subject)])
            })?;
            let view = imported.native_view();
            if let Some(existing) = registry.get_pack(&view.id) {
                let source = registry
                    .legacy
                    .as_ref()
                    .unwrap()
                    .iter()
                    .find(|p| p.native_view().id == view.id)
                    .unwrap();
                if source.original_document() == imported.original_document() {
                    continue;
                }
                return Err(CheckError(vec![Issue::error(
                    "RELATION_PACK_CONFLICT",
                    if existing.version != view.version {
                        format!(
                            "Relation pack {} is already registered at version {}",
                            view.id, existing.version
                        )
                    } else {
                        format!(
                            "Relation pack {}@{} conflicts with its registered definition",
                            view.id, view.version
                        )
                    },
                    &view.id,
                )]));
            }
            for relation in &view.relations {
                if !relations.insert(relation.id.clone()) {
                    return Err(CheckError(vec![Issue::error(
                        "DUPLICATE_RELATION",
                        format!("Relation {} is already registered", relation.id),
                        &relation.id,
                    )]));
                }
            }
            registry.packs.push(view.clone());
            registry.legacy.as_mut().unwrap().push(imported);
            crate::laws::validate_with_digests(&registry.packs, |index| {
                Ok(registry.legacy.as_ref().unwrap()[index]
                    .original_digest()
                    .to_owned())
            })?;
        }
        Ok(registry)
    }

    /// Original envelopes and addresses for imported snapshots. Ordinary modern
    /// registries return None; this data grants no checked/admitted capability.
    pub fn imported_packs(&self) -> Option<&[ImportedLegacyRelationPack]> {
        self.legacy.as_deref()
    }

    pub fn register_pack(&mut self, pack: RelationPack) -> Result<(), CheckError> {
        if self.legacy.is_some() {
            return Err(CheckError(vec![Issue::error(
                "LEGACY_REGISTRY_SNAPSHOT",
                "An imported legacy registry is read-only; construct a new snapshot to change its packs",
                &pack.id,
            )]));
        }
        if let Some(existing) = self.get_pack(&pack.id) {
            if existing == &pack {
                return Ok(());
            }
            return Err(CheckError(vec![Issue::error(
                "RELATION_PACK_CONFLICT",
                if existing.version != pack.version {
                    format!(
                        "Relation pack {} is already registered at version {}",
                        pack.id, existing.version
                    )
                } else {
                    format!(
                        "Relation pack {}@{} conflicts with its registered definition",
                        pack.id, pack.version
                    )
                },
                &pack.id,
            )]));
        }
        let mut proposed = self.packs.clone();
        proposed.push(pack);
        let empty: GraphDocument = parse(br#"{"schemaVersion":"0.1.0","documentType":"graph","id":"urn:patamaps:registry:validation","namespace":"registry","entities":[],"mappings":[],"authorities":[]}"#)?;
        CheckedGraph::check(empty, proposed.clone())?;
        self.packs = proposed;
        Ok(())
    }

    pub fn get_pack(&self, id: &str) -> Option<&RelationPack> {
        self.packs.iter().find(|pack| pack.id == id)
    }

    pub fn has_pack(&self, id: &str, version: Option<&str>) -> bool {
        self.get_pack(id).is_some_and(|pack| {
            version.is_none_or(|version| version.is_empty() || pack.version == version)
        })
    }

    pub fn get(&self, id: &str) -> Option<&Relation> {
        self.all().find(|relation| relation.id == id)
    }

    pub fn all(&self) -> impl Iterator<Item = &Relation> {
        self.packs.iter().flat_map(|pack| &pack.relations)
    }

    pub fn all_packs(&self) -> &[RelationPack] {
        &self.packs
    }

    pub fn executable_packs(&self) -> impl Iterator<Item = &RelationPack> {
        self.packs.iter().filter(|pack| pack.laws.is_some())
    }

    pub fn get_law(&self, id: &str) -> Option<(&RelationPack, &RelationLaw)> {
        self.executable_packs().find_map(|pack| {
            pack.laws
                .as_ref()?
                .iter()
                .find(|law| law.id == id)
                .map(|law| (pack, law))
        })
    }
}
