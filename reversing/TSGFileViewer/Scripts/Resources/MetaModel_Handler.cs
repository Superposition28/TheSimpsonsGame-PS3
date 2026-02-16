using Assets.Scripts.Resources;
using RWReader;
using RWReader.Sections;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Unity.VisualScripting;
using UnityEditor;
using UnityEditor.Experimental.GraphView;
using UnityEngine;
using UnityEngine.Rendering;
using static SimGroup;

namespace Assets.Scripts.ResourceHandlers
{
	public class MetaModel_Handler : ResourceHandler
	{
		public Dictionary<Guid128, MetaModel> MetaModels = new();
		public List<Guid128> DebugList = new();
		public List<MetaModel> DebugList2 = new();

		public override void HandleBytes(byte[] data, Guid128 guid, string strFilePath)
		{
			//Debug.Log($"Loading metamodel guid:{guid}, size = {data.Length}");

			var mm = new MetaModel();
			mm.STRFile = strFilePath;
			mm.GUID = guid;
			mm.Bytes = data;

			var stream = new MemoryStream(data);
			var reader = new BinaryReader(stream);

			mm.m_magicNumber = reader.ReadUInt32BigEndian();
			if (mm.m_magicNumber != 0x4D4D646C)
			{
				throw new NotImplementedException($"magic is {mm.m_magicNumber} instead of {0x4D4D646C}");
			}

			mm.m_version = reader.ReadUInt32BigEndian();
			if (mm.m_version != 0xA)
			{
				throw new NotImplementedException($"MM version is {mm.m_version}!");
			}

			mm.m_size = reader.ReadUInt32BigEndian();
			mm.m_flags = reader.ReadUInt32BigEndian();
			mm.m_guid = new Guid128(reader);
			mm.m_uName = reader.ReadUInt32BigEndian();
			mm.m_uPath = reader.ReadUInt32BigEndian();
			mm.m_uSourcePath = reader.ReadUInt32BigEndian();

			var assetOffset = reader.ReadInt32BigEndian();
			var stateOffset = reader.ReadInt32BigEndian();
			var variableOffset = reader.ReadInt32BigEndian();
			var attributeOffset = reader.ReadInt32BigEndian();
			var predicateOffset = reader.ReadInt32BigEndian();
			var partOffset = reader.ReadInt32BigEndian();

			mm.m_pAttrData = reader.ReadInt32BigEndian();
			mm.m_pUserData = reader.ReadInt32BigEndian();
			//Debug.Log($"attr data: {mm.m_pAttrData}, user data: {mm.m_pUserData}");

			mm.m_nAssets = reader.ReadUInt16BigEndian();
			mm.Assets = new MetaModel.MM_Asset[mm.m_nAssets];
			mm.m_nStates = reader.ReadUInt16BigEndian();
			mm.States = new MetaModel.MM_State[mm.m_nStates];
			mm.m_nVariables = reader.ReadUInt16BigEndian();
			mm.Variables = new MetaModel.MM_Variable[mm.m_nVariables];
			mm.m_nAttributes = reader.ReadUInt16BigEndian();
			mm.Attributes = new MetaModel.MM_Attribute[mm.m_nAttributes];
			mm.m_nPredicates = reader.ReadUInt16BigEndian();
			mm.Predicates = new MetaModel.MM_Predicate[mm.m_nPredicates];
			mm.m_nParts = reader.ReadUInt16BigEndian();
			mm.Parts = new MetaModel.MM_Object[mm.m_nParts];

			// ASSETS
			//Debug.Log("Reading assets");
			mm.Assets = new MetaModel.MM_Asset[mm.m_nAssets];
			reader.BaseStream.Position = assetOffset;
			for (var i = 0; i < mm.m_nAssets; i++)
			{
				var asset = new MetaModel.MM_Asset();
				asset.Address = reader.BaseStream.Position;

				asset.m_uName = reader.ReadUInt32BigEndian();
				asset.m_uPath = reader.ReadUInt32BigEndian();
				asset.m_typeID = reader.ReadUInt32BigEndian();
				asset.m_GUID = new Guid128(reader);
				asset.m_pUserData = reader.ReadInt32BigEndian();

				mm.Assets[i] = asset;
			}

			// STATES
			reader.BaseStream.Position = stateOffset;
			for (var i = 0; i < mm.m_nStates; i++)
			{
				var state = new MetaModel.MM_State();

				// mm_object
				state.Address = reader.BaseStream.Position;
				state.m_classID = reader.ReadUInt32BigEndian();
				state.m_pClassName = reader.ReadNullTerminatedStringAtPointer();
				state.m_pName = reader.ReadNullTerminatedStringAtPointer();
				state.attributeArrOffset = reader.ReadInt32BigEndian(); // double pointer
				state.m_nAttributes = reader.ReadUInt16BigEndian();
				state.m_objectType = (MetaModel.MM_ObjectType)reader.ReadUInt16BigEndian();

				// mm_state
				state.partArrOffset = reader.ReadInt32BigEndian(); // double pointer
				state.predicateArrOffset = reader.ReadInt32BigEndian(); // double pointer
				state.m_nParts = reader.ReadUInt16BigEndian();
				state.m_nPredicates = reader.ReadUInt16BigEndian();

				mm.States[i] = state;
			}

			// VARIABLES
			//Debug.Log("Reading variables");
			reader.BaseStream.Position = variableOffset;
			for (var i = 0; i < mm.m_nVariables; i++)
			{
				var variable = new MetaModel.MM_Variable();
				variable.Address = reader.BaseStream.Position;

				variable.m_pName = reader.ReadNullTerminatedStringAtPointer();
				variable.m_ID = reader.ReadUInt32BigEndian();
				variable.m_valueType = (MetaModel.MM_ValueType)reader.ReadUInt16BigEndian();
				reader.ReadUInt16BigEndian(); // m_pad

				//Debug.Log($"Name: {variable.m_pName}, ID:{variable.m_ID}, ValueType:{variable.m_valueType}");
				mm.Variables[i] = variable;
			}

			// ATTRIBUTES
			//Debug.Log("Reading attributes");
			reader.BaseStream.Position = attributeOffset;
			for (var i = 0; i < mm.m_nAttributes; i++)
			{
				var attribute = new MetaModel.MM_Attribute();
				attribute.AttachedMetaModel = mm;
				attribute.Address = reader.BaseStream.Position;

				// mm_value
				attribute.Bytes = reader.ReadBytes(4);

				// mm_attribute
				attribute.m_pName = reader.ReadNullTerminatedStringAtPointer();
				attribute.m_pScope = reader.ReadNullTerminatedStringAtPointer();
				attribute.m_uIndex = reader.ReadUInt32BigEndian();
				attribute.m_ID = reader.ReadUInt32BigEndian();
				attribute.m_valueType = (MetaModel.MM_ValueType)reader.ReadInt32BigEndian();

				mm.Attributes[i] = attribute;
			}

			// PREDICATES
			//Debug.Log("Reading predicates");
			reader.BaseStream.Position = predicateOffset;
			for (var i = 0; i < mm.m_nPredicates; i++)
			{
				var pred = new MetaModel.MM_Predicate();
				pred.AttachedMetaModel = mm;
				pred.Address = reader.BaseStream.Position;

				// mm_value
				pred.Bytes = reader.ReadBytes(4);

				// mm_predicate
				pred.variableAddress = reader.ReadInt32BigEndian();
				pred.m_compareOp = (MetaModel.CompareOp)reader.ReadUInt16BigEndian();
				reader.ReadUInt16BigEndian(); // pad

				mm.Predicates[i] = pred;
			}

			// PARTS
			//Debug.Log($"Reading parts - {mm.m_nParts} parts");
			reader.BaseStream.Position = partOffset;
			for (var i = 0; i < mm.m_nParts; i++)
			{
				var part = new MetaModel.MM_Object();
				part.Address = reader.BaseStream.Position;

				// mm_object
				part.m_classID = reader.ReadUInt32BigEndian();
				part.m_pClassName = reader.ReadNullTerminatedStringAtPointer();
				part.m_pName = reader.ReadNullTerminatedStringAtPointer();
				part.attributeArrOffset = reader.ReadInt32BigEndian(); // double pointer
				part.m_nAttributes = reader.ReadUInt16BigEndian();
				part.m_objectType = (MetaModel.MM_ObjectType)reader.ReadUInt16BigEndian();

				//Debug.Log($"PART AT {part.Address} - Class:{part.m_pClassName}, Name:{part.m_pName}");

				mm.Parts[i] = part;
			}

			// --- Fixups ---

			/*
			 * All MM_Objects need their attribute arrays filled
			 * - Part
			 * - MM_State
			 */

			foreach (var part in mm.Parts)
			{
				part.m_pAttributeArr = new MetaModel.MM_Attribute[part.m_nAttributes];
				reader.BaseStream.Position = part.attributeArrOffset;
				for (var i = 0; i < part.m_nAttributes; i++)
				{
					var attrAddress = reader.ReadInt32BigEndian();
					part.m_pAttributeArr[i] = mm.Attributes.First(x => x.Address == attrAddress);
				}
			}

			foreach (var state in mm.States)
			{
				state.m_pAttributeArr = new MetaModel.MM_Attribute[state.m_nAttributes];
				reader.BaseStream.Position = state.attributeArrOffset;
				for (var i = 0; i < state.m_nAttributes; i++)
				{
					var attrAddress = reader.ReadInt32BigEndian();
					state.m_pAttributeArr[i] = mm.Attributes.First(x => x.Address == attrAddress);
				}
			}

			/*
			 * MM_States need their part and predicate arrays filled
			 */

			foreach (var state in mm.States)
			{
				//Debug.Log($"Fixing up state {state.m_pName} - nParts: {state.m_nParts}, part array offset: {state.partArrOffset}");

				state.m_pPartArr = new MetaModel.MM_Object[state.m_nParts];
				reader.BaseStream.Position = state.partArrOffset;
				for (var i = 0; i < state.m_nParts; i++)
				{
					var partAddress = reader.ReadInt32BigEndian();
					state.m_pPartArr[i] = mm.Parts.First(x => x.Address == partAddress);
				}

				state.m_pPredicateArr = new MetaModel.MM_Predicate[state.m_nPredicates];
				reader.BaseStream.Position = state.predicateArrOffset;
				for (var i = 0; i < state.m_nPredicates; i++)
				{
					var predicateAddress = reader.ReadInt32BigEndian();
					state.m_pPredicateArr[i] = mm.Predicates.First(x => x.Address == predicateAddress);
				}
			}

			/*
			 * MM_Predicates need their variable reference filled
			 */

			foreach (var pred in mm.Predicates)
			{
				var variablePosition = pred.variableAddress;
				pred.m_pVariable = mm.Variables.First(x => x.Address == variablePosition);
			}

			reader.Dispose();
			stream.Dispose();

			MetaModels.Add(guid, mm);
			DebugList.Add(guid);
			DebugList2.Add(mm);
			//Debug.Log($"Added {guid}");
		}

		public override IEnumerable<Resource> GetResources()
		{
			return MetaModels.Values.ToList();
		}
	}
}