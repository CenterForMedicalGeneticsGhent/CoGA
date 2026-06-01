import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

interface PedRow {
  fid: string;
  iid: string;
  pid: string;
  mid: string;
  sex: string;
  phen: string;
}

interface PedigreeMember {
  sample_id: string;
  role?: string | null;
  carrier_status?: "unknown" | "not_carrier" | "carrier" | boolean | null;
  carrier_type?: "obligate" | "proven" | "reported" | "inferred" | null;
  clinical_status?: string | null;
  sex?: string | null;
  affected?: boolean | null;
}

interface PedigreeRelationship {
  relationship_type: "parent_child" | "couple";
  sample_id_a: string;
  sample_id_b: string;
  role_a?: string | null;
  role_b?: string | null;
  metadata?: Record<string, unknown> | null;
}

interface Props {
  rows: PedRow[];
  members?: PedigreeMember[];
  relationships?: PedigreeRelationship[];
  inheritanceModel?: string | null;
}

type ParentInfo = {
  father?: string;
  mother?: string;
  others: string[];
};

type FamilyUnit = {
  key: string;
  parents: string[];
  children: string[];
};

const NODE_SIZE = 20;
const GEN_VERTICAL_GAP = 100;
const ROOT_HORIZONTAL_GAP = 56;
const PERSON_HORIZONTAL_GAP = 32;
const CHILD_HORIZONTAL_GAP = 32;
const COUPLE_GAP = 50;
const SIBLING_LINE_OFFSET = 20;

const isAffectedPhenotype = (phenotype: string): boolean => phenotype === "2";

const sexCodeFromMember = (member?: PedigreeMember): string => {
  if (member?.sex === "male") return "1";
  if (member?.sex === "female") return "2";
  return "0";
};

const phenotypeFromMember = (member?: PedigreeMember): string => {
  if (member?.clinical_status === "affected" || member?.affected) return "2";
  if (member?.clinical_status === "unaffected") return "1";
  return "0";
};

const familyKey = (parents: string[]): string => [...parents].sort().join("|");

const addUnique = (values: string[], value?: string | null) => {
  const cleaned = (value || "").trim();
  if (cleaned && cleaned !== "0" && !values.includes(cleaned)) {
    values.push(cleaned);
  }
};

const isCarrierStatus = (status: PedigreeMember["carrier_status"]): boolean =>
  status === true || status === "carrier";

const carrierFillFor = (carrierType?: PedigreeMember["carrier_type"]): string => {
  if (carrierType === "obligate") return "#2563eb";
  if (carrierType === "reported") return "#7c3aed";
  if (carrierType === "inferred") return "#0f766e";
  return "black";
};

const Pedigree: React.FC<Props> = ({
  rows,
  members = [],
  relationships = [],
  inheritanceModel,
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const memberMap = new Map(members.map((member) => [member.sample_id, member]));
    const normalizedRows = [...rows];
    const rowMap = new Map(normalizedRows.map((row) => [row.iid, row]));

    members.forEach((member) => {
      if (!rowMap.has(member.sample_id)) {
        const row = {
          fid: rows[0]?.fid || "FAM",
          iid: member.sample_id,
          pid: "0",
          mid: "0",
          sex: sexCodeFromMember(member),
          phen: phenotypeFromMember(member),
        };
        normalizedRows.push(row);
        rowMap.set(row.iid, row);
      }
    });

    const normalizedInheritance = (inheritanceModel || "").trim().toUpperCase();
    const parentInfoByChild = new Map<string, ParentInfo>();
    const ensureParentInfo = (childId: string): ParentInfo => {
      const existing = parentInfoByChild.get(childId);
      if (existing) return existing;
      const created = { others: [] };
      parentInfoByChild.set(childId, created);
      return created;
    };

    normalizedRows.forEach((row) => {
      const info = ensureParentInfo(row.iid);
      if (row.pid && row.pid !== "0") info.father = row.pid;
      if (row.mid && row.mid !== "0") info.mother = row.mid;
    });

    relationships.forEach((relationship) => {
      if (relationship.relationship_type !== "parent_child") return;
      const parentId = relationship.sample_id_a;
      const childId = relationship.sample_id_b;
      if (!parentId || !childId || parentId === childId) return;
      const info = ensureParentInfo(childId);
      const role = (relationship.role_a || "").toLowerCase();
      if (role === "father") {
        info.father = parentId;
      } else if (role === "mother") {
        info.mother = parentId;
      } else {
        addUnique(info.others, parentId);
      }
    });

    const parentIdsFor = (childId: string): string[] => {
      const info = parentInfoByChild.get(childId);
      if (!info) return [];
      const parents: string[] = [];
      addUnique(parents, info.father);
      addUnique(parents, info.mother);
      info.others.forEach((parentId) => addUnique(parents, parentId));
      return parents;
    };

    const familyUnits = new Map<string, FamilyUnit>();
    normalizedRows.forEach((row) => {
      const parents = parentIdsFor(row.iid);
      if (!parents.length) return;
      const key = familyKey(parents);
      if (!familyUnits.has(key)) {
        familyUnits.set(key, { key, parents, children: [] });
      }
      addUnique(familyUnits.get(key)!.children, row.iid);
    });

    relationships.forEach((relationship) => {
      if (relationship.relationship_type !== "couple") return;
      const parents: string[] = [];
      addUnique(parents, relationship.sample_id_a);
      addUnique(parents, relationship.sample_id_b);
      if (parents.length !== 2) return;
      const key = familyKey(parents);
      if (!familyUnits.has(key)) {
        familyUnits.set(key, { key, parents, children: [] });
      }
    });

    const generationCache = new Map<string, number>();
    const visiting = new Set<string>();
    const getGeneration = (iid: string): number => {
      if (generationCache.has(iid)) return generationCache.get(iid)!;
      if (visiting.has(iid)) return 0;
      visiting.add(iid);
      const parents = parentIdsFor(iid);
      const generation = parents.length
        ? Math.max(...parents.map((parentId) => getGeneration(parentId) + 1))
        : 0;
      visiting.delete(iid);
      generationCache.set(iid, generation);
      return generation;
    };

    normalizedRows.forEach((row) => getGeneration(row.iid));

    const positions = new Map<string, { x: number; y: number; generation: number }>();
    const occupiedByGeneration = new Map<number, number[]>();
    const nextXByGeneration = new Map<number, number>();

    const isFree = (generation: number, x: number): boolean =>
      (occupiedByGeneration.get(generation) || []).every(
        (existingX) => Math.abs(existingX - x) >= PERSON_HORIZONTAL_GAP,
      );

    const reserveX = (generation: number, desiredX?: number): number => {
      const base = Number.isFinite(desiredX)
        ? Number(desiredX)
        : nextXByGeneration.get(generation) ?? 50;
      for (let step = 0; step < 200; step += 1) {
        const candidates = step === 0
          ? [base]
          : [base + step * PERSON_HORIZONTAL_GAP, base - step * PERSON_HORIZONTAL_GAP];
        const found = candidates.find((candidate) => isFree(generation, candidate));
        if (found !== undefined) {
          occupiedByGeneration.set(generation, [
            ...(occupiedByGeneration.get(generation) || []),
            found,
          ]);
          nextXByGeneration.set(
            generation,
            Math.max(nextXByGeneration.get(generation) ?? 50, found + ROOT_HORIZONTAL_GAP),
          );
          return found;
        }
      }
      const fallback = (nextXByGeneration.get(generation) ?? 50) + ROOT_HORIZONTAL_GAP;
      occupiedByGeneration.set(generation, [
        ...(occupiedByGeneration.get(generation) || []),
        fallback,
      ]);
      nextXByGeneration.set(generation, fallback + ROOT_HORIZONTAL_GAP);
      return fallback;
    };

    const placePerson = (sampleId: string, generation: number, desiredX?: number) => {
      if (positions.has(sampleId)) return positions.get(sampleId)!;
      const x = reserveX(generation, desiredX);
      const position = {
        x,
        y: generation * GEN_VERTICAL_GAP + 50,
        generation,
      };
      positions.set(sampleId, position);
      return position;
    };

    const orderedFamilyUnits = [...familyUnits.values()].sort((left, right) => {
      const leftGeneration = Math.min(...left.parents.map((parentId) => getGeneration(parentId)));
      const rightGeneration = Math.min(...right.parents.map((parentId) => getGeneration(parentId)));
      if (leftGeneration !== rightGeneration) return leftGeneration - rightGeneration;
      return left.key.localeCompare(right.key);
    });

    orderedFamilyUnits.forEach((unit) => {
      const parentGeneration = unit.parents.length
        ? Math.min(...unit.parents.map((parentId) => getGeneration(parentId)))
        : Math.max(0, Math.min(...unit.children.map((childId) => getGeneration(childId))) - 1);
      if (unit.parents.length === 1) {
        placePerson(unit.parents[0], parentGeneration);
      } else if (unit.parents.length >= 2) {
        const [leftParent, rightParent] = unit.parents;
        const leftPosition = positions.get(leftParent);
        const rightPosition = positions.get(rightParent);
        if (!leftPosition && !rightPosition) {
          const leftX = nextXByGeneration.get(parentGeneration) ?? 50;
          placePerson(leftParent, parentGeneration, leftX);
          placePerson(rightParent, parentGeneration, leftX + COUPLE_GAP);
        } else if (leftPosition && !rightPosition) {
          placePerson(rightParent, parentGeneration, leftPosition.x + COUPLE_GAP);
        } else if (!leftPosition && rightPosition) {
          placePerson(leftParent, parentGeneration, rightPosition.x - COUPLE_GAP);
        }
      }

      const placedParents = unit.parents
        .map((parentId) => positions.get(parentId))
        .filter((position): position is { x: number; y: number; generation: number } => Boolean(position));
      const centerX = placedParents.length
        ? d3.mean(placedParents, (position) => position.x) ?? undefined
        : undefined;

      unit.children.forEach((childId, index) => {
        const childGeneration = Math.max(parentGeneration + 1, getGeneration(childId));
        const offset = (index - (unit.children.length - 1) / 2) * CHILD_HORIZONTAL_GAP;
        placePerson(childId, childGeneration, centerX === undefined ? undefined : centerX + offset);
      });
    });

    normalizedRows.forEach((row) => {
      placePerson(row.iid, getGeneration(row.iid));
    });

    let minX = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    positions.forEach((position) => {
      minX = Math.min(minX, position.x);
      maxX = Math.max(maxX, position.x);
      maxY = Math.max(maxY, position.y);
    });
    if (!Number.isFinite(minX)) {
      minX = 0;
      maxX = 0;
      maxY = 0;
    }
    const offsetX = -minX + 50;
    positions.forEach((position) => {
      position.x += offsetX;
    });
    const width = maxX - minX + 100;
    const height = maxY + 50;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    familyUnits.forEach((unit) => {
      const parentPositions = unit.parents
        .map((parentId) => positions.get(parentId))
        .filter((position): position is { x: number; y: number; generation: number } => Boolean(position));
      if (!parentPositions.length) return;
      const parentY = parentPositions[0].y;
      const parentBottomY = parentY + NODE_SIZE / 2;
      const centerX = d3.mean(parentPositions, (position) => position.x) ?? parentPositions[0].x;

      if (parentPositions.length >= 2) {
        const orderedParents = [...parentPositions].sort((left, right) => left.x - right.x);
        svg
          .append("line")
          .attr("x1", orderedParents[0].x)
          .attr("y1", orderedParents[0].y)
          .attr("x2", orderedParents[orderedParents.length - 1].x)
          .attr("y2", orderedParents[orderedParents.length - 1].y)
          .attr("stroke", "black");
      }

      const childPositions = unit.children
        .map((childId) => positions.get(childId))
        .filter((position): position is { x: number; y: number; generation: number } => Boolean(position))
        .sort((left, right) => left.x - right.x);
      if (!childPositions.length) return;

      if (childPositions.length === 1) {
        const childPosition = childPositions[0];
        svg
          .append("line")
          .attr("x1", centerX)
          .attr("y1", parentBottomY)
          .attr("x2", centerX)
          .attr("y2", childPosition.y - NODE_SIZE / 2)
          .attr("stroke", "black");
      } else {
        const siblingLineY = parentBottomY + SIBLING_LINE_OFFSET;
        svg
          .append("line")
          .attr("x1", centerX)
          .attr("y1", parentBottomY)
          .attr("x2", centerX)
          .attr("y2", siblingLineY)
          .attr("stroke", "black");
        svg
          .append("line")
          .attr("x1", childPositions[0].x)
          .attr("y1", siblingLineY)
          .attr("x2", childPositions[childPositions.length - 1].x)
          .attr("y2", siblingLineY)
          .attr("stroke", "black");
        childPositions.forEach((childPosition) => {
          svg
            .append("line")
            .attr("x1", childPosition.x)
            .attr("y1", siblingLineY)
            .attr("x2", childPosition.x)
            .attr("y2", childPosition.y - NODE_SIZE / 2)
            .attr("stroke", "black");
        });
      }
    });

    normalizedRows.forEach((row) => {
      const position = positions.get(row.iid);
      if (!position) return;
      const member = memberMap.get(row.iid);
      const affected = isAffectedPhenotype(row.phen) || member?.clinical_status === "affected";
      const carrier = isCarrierStatus(member?.carrier_status);
      const xLinkedRecessiveFemaleCarrier = carrier && normalizedInheritance === "XLR" && row.sex === "2";
      const fill = affected ? "black" : "white";
      const stroke = "black";
      const group = svg
        .append("g")
        .attr("data-pedigree-node", row.iid)
        .attr("transform", `translate(${position.x}, ${position.y})`);

      const drawCarrierHalfFill = (shape: d3.Selection<any, unknown, null, undefined>) => {
        if (!carrier || affected || xLinkedRecessiveFemaleCarrier) return;
        const clipId = `pedigree-carrier-${row.iid.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
        svg
          .append("clipPath")
          .attr("id", clipId)
          .append("rect")
          .attr("x", position.x - NODE_SIZE / 2)
          .attr("y", position.y - NODE_SIZE / 2)
          .attr("width", NODE_SIZE / 2)
          .attr("height", NODE_SIZE);
        shape
          .clone(true)
          .attr("fill", carrierFillFor(member?.carrier_type))
          .attr("stroke", "none")
          .attr("clip-path", `url(#${clipId})`);
      };

      if (row.sex === "1") {
        const shape = group
          .append("rect")
          .attr("x", -NODE_SIZE / 2)
          .attr("y", -NODE_SIZE / 2)
          .attr("width", NODE_SIZE)
          .attr("height", NODE_SIZE)
          .attr("fill", fill)
          .attr("stroke", stroke);
        drawCarrierHalfFill(shape);
      } else if (row.sex === "2") {
        const shape = group
          .append("circle")
          .attr("cx", 0)
          .attr("cy", 0)
          .attr("r", NODE_SIZE / 2)
          .attr("fill", fill)
          .attr("stroke", stroke);
        drawCarrierHalfFill(shape);
        if (xLinkedRecessiveFemaleCarrier && !affected) {
          group
            .append("circle")
            .attr("cx", 0)
            .attr("cy", 0)
            .attr("r", NODE_SIZE / 4)
            .attr("fill", carrierFillFor(member?.carrier_type))
            .attr("stroke", "none");
        }
      } else {
        const diamondPath =
          `M0 ${-NODE_SIZE / 2} ` +
          `L${NODE_SIZE / 2} 0 ` +
          `L0 ${NODE_SIZE / 2} ` +
          `L${-NODE_SIZE / 2} 0 Z`;
        const shape = group
          .append("path")
          .attr("d", diamondPath)
          .attr("fill", fill)
          .attr("stroke", stroke);
        drawCarrierHalfFill(shape);
      }

      group
        .append("text")
        .attr("x", 0)
        .attr("y", NODE_SIZE)
        .attr("text-anchor", "middle")
        .attr("font-size", member?.role === "embryo" ? 7 : 8)
        .text(row.iid);
    });
  }, [rows, members, relationships, inheritanceModel]);

  return (
    <svg
      ref={svgRef}
      className="pedigree-svg"
    />
  );
};

export default Pedigree;
