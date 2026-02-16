using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Unity.Properties;

namespace Assets.Scripts.Resources
{
	[Serializable]
	public class MetaModel : Resource
	{
		public byte[] Bytes;

		[Serializable]
		public class MM_Asset
		{
			[NonSerialized]
			public long Address;

			public uint m_uName;
			public uint m_uPath;
			public uint m_typeID;
			public Guid128 m_GUID;
			public int m_pUserData;
		}

		[Serializable]
		public class MM_Object
		{
			[NonSerialized]
			public long Address;

			public uint m_classID;
			public string m_pClassName;
			public string m_pName;
			public MM_Attribute[] m_pAttributeArr;

			[NonSerialized] // double pointer
			public int attributeArrOffset;

			public ushort m_nAttributes;
			public MM_ObjectType m_objectType;
		}

		[Serializable]
		public class MM_State : MM_Object
		{
			public MM_Object[] m_pPartArr;
			public MM_Predicate[] m_pPredicateArr;

			[NonSerialized] // double pointer
			public int partArrOffset;
			[NonSerialized] // double pointer
			public int predicateArrOffset;

			public ushort m_nParts;
			public ushort m_nPredicates;
		}

		[Serializable]
		public class MM_Variable
		{
			[NonSerialized]
			public long Address;

			public string m_pName;
			public uint m_ID;
			public MM_ValueType m_valueType;
		}

		[Serializable]
		public class MM_Value
		{
			[NonSerialized]
			public MetaModel AttachedMetaModel;

			[NonSerialized]
			public long Address;

			[NonSerialized]
			public byte[] Bytes = new byte[4];

			public bool GetBool()
			{
				return Bytes[0] == 1;
			}

			public uint GetUInt()
			{
				return BinaryPrimitives.ReadUInt32BigEndian(Bytes);
			}

			public float GetFloat()
			{
				return Extensions.ReadSingleBigEndian(Bytes);
			}

			public string GetString()
			{
				throw new NotImplementedException();
			}

			public MM_Asset GetAsset()
			{
				return AttachedMetaModel.Assets.First(x => x.Address == GetUInt());
			}

			public RwMatrixTag GetMatrix()
			{
				var stream = new MemoryStream(AttachedMetaModel.Bytes);
				var reader = new BinaryReader(stream);

				reader.BaseStream.Position = GetUInt();
				var matrix = new RwMatrixTag(reader);

				reader.Dispose();
				stream.Dispose();
				return matrix;
			}
		}

		[Serializable]
		public class MM_Attribute : MM_Value
		{
			public string m_pName;
			public string m_pScope;
			public uint m_uIndex;
			public uint m_ID;
			public MM_ValueType m_valueType;
		}

		[Serializable]
		public class MM_Predicate : MM_Value
		{
			public MM_Variable m_pVariable;

			[NonSerialized]
			public int variableAddress;

			public CompareOp m_compareOp;
		}

		[Flags]
		public enum MM_ValueType
		{
			BOGUS = 0x0,
			BOOL = 0x1,
			UINT32 = 0x2,
			FLOAT = 0x4,
			STRING = 0x8,
			ASSET = 0x10,
			MATRIX = 0x20,
			PREDICATE_MASK = BOOL | UINT32 | FLOAT,
			ATTRIBUTE_MASK = BOOL | UINT32 | FLOAT | STRING | ASSET | MATRIX,
			ATTRIBUTE_FIXUP = STRING | ASSET | MATRIX,
			FORCEINT = 0x7FFFFFFF // ??
		}

		[Flags]
		public enum MM_ObjectType
		{
			BOGUS = 0x0,
			STATE = 0x1,
			SIMPLE_PART = 0x2,
			METAMODEL_PART = 0x4,
			ENTITY_PART = 0x8,
			PART_OBJECT_MASK = SIMPLE_PART | METAMODEL_PART | ENTITY_PART
		}

		public enum CompareOp
		{
			BOGUS = -1,
			GT,
			LT,
			GE,
			LE,
			EQ,
			NEQ
		}

		public uint m_magicNumber;
		public uint m_version;
		public uint m_size;
		public uint m_flags;
		public Guid128 m_guid;
		public uint m_uName;
		public uint m_uPath;
		public uint m_uSourcePath;

		public int m_pAttrData;
		public int m_pUserData;

		public MM_Asset[] Assets;
		public MM_State[] States;
		public MM_Variable[] Variables;
		public MM_Attribute[] Attributes;
		public MM_Predicate[] Predicates;
		public MM_Object[] Parts;

		public ushort m_nAssets;
		public ushort m_nStates;
		public ushort m_nVariables;
		public ushort m_nAttributes;
		public ushort m_nPredicates;
		public ushort m_nParts;
	}
}
